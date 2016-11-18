package hex.tree;

import hex.genmodel.utils.DistributionFamily;
import jsr166y.CountedCompleter;
import water.*;
import water.fvec.*;
import water.util.ArrayUtils;

import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;

import water.util.VecUtils;

/**
 * Created by tomas on 10/28/16.
 *
 * Score and Build Histogram.
 *
 * This is an updated version ditching histogram sharing (still optional) to improve perfomance on multi-cpu systems (witnessed speedup of up to 4x).
 *
 * NOTE: unlike standard MRTask, launch via dfork2 instead of doAll/dfork. Has custom 2-phase local mapreduce task.
 *
 * <p>Fuse 2 conceptual passes into one (MRTask):
 *
 * <dl>
 *
 * <dt>Pass 1:</dt><dd>Score a prior partially-built tree model, and make new Node assignments to
 * every row.  This involves pulling out the current assigned DecidedNode,
 * "scoring" the row against that Node's decision criteria, and assigning the
 * row to a new child UndecidedNode (and giving it an improved prediction).</dd>
 *
 * <dt>Pass 2:</dt><dd>Build new summary DHistograms on the new child UndecidedNodes
 * every row got assigned into.  Collect counts, mean, variance, min,
 * max per bin, per column.</dd>
 * </dl>
 *
 * The 2 passes are executed (locally) in sequence.
 *
 * <p>The result is a set of DHistogram arrays; one DHistogram array for each
 * unique 'leaf' in the tree being histogramed in parallel.  These have node
 * ID's (nids) from 'leaf' to 'tree._len'.  Each DHistogram array is for all
 * the columns in that 'leaf'.
 *
 * <p>The other result is a prediction "score" for the whole dataset, based on
 * the previous passes' DHistograms.
 *
 *
 * No CAS update:
 *
 * Sharing the histograms proved to be a performance problem on larger multi-cpu machines with many running threads, CAS was the bottleneck.
 *
 * To remove the CAS while minimizing the memory overhead (private copies of histograms), phase 2 is paralellized both over columns and rows.
 * Each column (block of columns) is processed in LocalMrTask.
 * Expected number of tasks running in parallel (and hence private Historgam copies made) is given by
 *
 *    exp(nthreads) = max(1,H2O.NUMCPUS - num_cols/COL_BLOCK_SZ)
 *
 */
public class ScoreBuildHistogram2 extends ScoreBuildHistogram {
  transient int []   _cids;
  transient Chunk[][] _chks;
  transient int [][] _nhs;
  transient int [][] _rss;
  Frame _fr2;

  private static int COL_BLOCK_SZ = 2;
  public ScoreBuildHistogram2(H2O.H2OCountedCompleter cc, int k, int ncols, int nbins, int nbins_cats, DTree tree, int leaf, DHistogram[][] hcs, DistributionFamily family, int weightIdx, int workIdx, int nidIdxs) {
    super(cc, k, ncols, nbins, nbins_cats, tree, leaf, hcs, family, weightIdx, workIdx, nidIdxs);
  }

  @Override
  public ScoreBuildHistogram dfork2(byte[] types, Frame fr, boolean run_local) {
    _fr2 = fr;
    dfork((Key[])null);
    return this;
  }

  @Override public void map(Chunk [] chks){
    // Even though this is an MRTask over a Frame, map(Chunk [] chks) should not be called for this task.
    //  Instead, we do a custom 2-stage local pass (launched from setupLocal) using LocalMR.
    //
    // There are 2 reasons for that:
    //    a) We have 2 local passes. 1st pass scores the trees and sorts rows, 2nd pass starts after the 1st pass is done and computes the histogram.
    //       Conceptually two tasks but since we do not need global result we want to do the two passes inside of 1 task - no need to insert extra communication overhead here.
    //    b) To reduce the memory overhead in pass 2(in case we're making private DHistogram copies).
    //       There is a private copy made for each task. MRTask forks one task per one line of chunks and we do not want to make too many copies.
    //       By reusing the same DHisto for multiple chunks we save memory and calls to reduce.
    //
    throw H2O.unimpl();
  }


  // Pass 1: Score a prior partially-built tree model, and make new Node
  // assignments to every row.  This involves pulling out the current
  // assigned DecidedNode, "scoring" the row against that Node's decision
  // criteria, and assigning the row to a new child UndecidedNode (and
  // giving it an improved prediction).
  // Pass 1: Score a prior partially-built tree model, and make new Node
  // assignments to every row.  This involves pulling out the current
  // assigned DecidedNode, "scoring" the row against that Node's decision
  // criteria, and assigning the row to a new child UndecidedNode (and
  // giving it an improved prediction).
  protected int[] score_decide(Chunk chks[], int nnids[]) {
    int [] res = nnids.clone();
    for( int row=0; row<nnids.length; row++ ) { // Over all rows
      int nid = nnids[row];          // Get Node to decide from
      if( isDecidedRow(nid)) {               // already done
        res[row] -= _leaf;
        continue;
      }
      // Score row against current decisions & assign new split
      boolean oob = isOOBRow(nid);
      if( oob ) nid = oob2Nid(nid); // sampled away - we track the position in the tree
      DTree.DecidedNode dn = _tree.decided(nid);
      if( dn == null || dn._split == null ) { // Might have a leftover non-split
        if( DTree.isRootNode(dn) ) { res[row] = nid - _leaf; continue; }
        nid = dn._pid;             // Use the parent split decision then
        int xnid = oob ? nid2Oob(nid) : nid;
        nnids[row] = xnid;
        res[row] = xnid - _leaf;
        dn = _tree.decided(nid); // Parent steers us
      }
      assert !isDecidedRow(nid);
      nid = dn.getChildNodeID(chks,row); // Move down the tree 1 level
      if( !isDecidedRow(nid) ) {
        if( oob ) nid = nid2Oob(nid); // Re-apply OOB encoding
        nnids[row] = nid;
      }
      res[row] = nid-_leaf;
    }
    return res;
  }

  @Override
  public void setupLocal() {
    addToPendingCount(1);
    // Init all the internal tree fields after shipping over the wire
    _tree.init_tree();
    _cids = VecUtils.getLocalChunkIds(_fr2.anyVec());
    _chks = new Chunk[_cids.length][_fr2.numCols()];
    _nhs = new int[_cids.length][];
    _rss = new int[_cids.length][];
    long [] espc = _fr2.anyVec().espc();
    int largestChunkSz = 0;
    for(int i = 1; i < espc.length; ++i){
      int sz = (int)(espc[i] - espc[i-1]);
      if(sz > largestChunkSz) largestChunkSz = sz;
    }
    final int fLargestChunkSz = largestChunkSz;

    final AtomicInteger cidx = new AtomicInteger(0);
    // First do the phase 1 on all local data
    new LocalMR(new MrFun(){
      // more or less copied from ScoreBuildHistogram
      private void map(int id, Chunk [] chks) {
        final C4VolatileChunk nids = (C4VolatileChunk) chks[_nidIdx];
        // Pass 1: Score a prior partially-built tree model, and make new Node
        // assignments to every row.  This involves pulling out the current
        // assigned DecidedNode, "scoring" the row against that Node's decision
        // criteria, and assigning the row to a new child UndecidedNode (and
        // giving it an improved prediction).
        int [] nnids;
        if( _leaf > 0)            // Prior pass exists?
          nnids = score_decide(chks,nids.getValues());
        else {                     // Just flag all the NA rows
          nnids = new int[nids._len];
          int [] is = nids.getValues();
          for (int row = 0; row < nids._len; row++) {
            if (isDecidedRow(is[row]))
              nnids[row] = DECIDED_ROW;
          }
        }
        // Pass 2: accumulate all rows, cols into histograms
        // Sort the rows by NID, so we visit all the same NIDs in a row
        // Find the count of unique NIDs in this chunk
        int nh[] = (_nhs[id] = new int[_hcs.length + 1]);
        for (int i : nnids)
          if (i >= 0)
            nh[i + 1]++;
        // Rollup the histogram of rows-per-NID in this chunk
        for (int i = 0; i < _hcs.length; i++) nh[i + 1] += nh[i];
        // Splat the rows into NID-groups
        int rows[] = (_rss[id] = new int[nnids.length]);
        for (int row = 0; row < nnids.length; row++)
          if (nnids[row] >= 0)
            rows[nh[nnids[row]]++] = row;
        // rows[] has Chunk-local ROW-numbers now, in-order, grouped by NID.
        // nh[] lists the start of each new NID, and is indexed by NID+1.
      }
      @Override
      protected void map(int id) {
        Vec[] vecs = _fr2.vecs();
        for(id = cidx.getAndIncrement(); id < _cids.length; id = cidx.getAndIncrement()) {
          int cidx = _cids[id];
          Chunk [] chks = _chks[id];
          for (int i = 0; i < chks.length; ++i)
            chks[i] = vecs[i].chunkForChunkIdx(cidx);
          map(id,chks);
        }
      }
    },new H2O.H2OCountedCompleter(this){
      public void onCompletion(CountedCompleter cc){
        int ncols = _ncols;
        int colBlockSz = Math.min(ncols,COL_BLOCK_SZ);
        for(int i = 0; i < ncols; i += colBlockSz) {
          ScoreBuildHistogram2.this.addToPendingCount(1);
          final int colFrom= i;
          final int colTo = Math.min(ncols,colFrom+colBlockSz);
          DHistogram[][] hcs = _hcs.clone();
          for(int j = 0; j < hcs.length; ++j)
            hcs[j] = Arrays.copyOfRange(hcs[j],colFrom,colTo);
            new LocalMR<ComputeHistoThread>(new ComputeHistoThread(hcs,colFrom,colTo,fLargestChunkSz,new AtomicInteger()), ScoreBuildHistogram2.this).fork();
        }
      }
    }).fork();
  }

  // Reduce for both local and remote
  private static void mergeHistos(DHistogram [][] hcs, DHistogram [][] hcs2){
    // Distributed histograms need a little work
    for( int i=0; i< hcs.length; i++ ) {
      DHistogram hs1[] = hcs[i], hs2[] = hcs2[i];
      if( hs1 == null ) hcs[i] = hs2;
      else if( hs2 != null )
        for( int j=0; j<hs1.length; j++ )
          if( hs1[j] == null ) hs1[j] = hs2[j];
          else if( hs2[j] != null ) {
            hs1[j].add(hs2[j]);
          }
    }
  }

  private class ComputeHistoThread extends MrFun<ComputeHistoThread> {
    final int _maxChunkSz;
    final int _colFrom, _colTo;
    final DHistogram [][] _lhcs;

    double [] _ys = null;
    AtomicInteger _cidx;

    ComputeHistoThread(DHistogram [][] hcs, int colFrom, int colTo, int maxChunkSz,AtomicInteger cidx){
      _lhcs = hcs; _colFrom = colFrom; _colTo = colTo; _maxChunkSz = maxChunkSz;
      _cidx = cidx;
    }

    @Override
    public ComputeHistoThread makeCopy() {
      ComputeHistoThread res = new ComputeHistoThread(ArrayUtils.deepClone(_lhcs),_colFrom,_colTo,_maxChunkSz,_cidx);
      return res;
    }


    @Override
    protected void map(int id){
      double [] cs = null;
      double [] ws = null;
      for(int i = _cidx.getAndIncrement(); i < _cids.length; i = _cidx.getAndIncrement()) {
        if(cs == null) {
          cs = MemoryManager.malloc8d(_maxChunkSz);
          ws = MemoryManager.malloc8d(_maxChunkSz);
          Arrays.fill(ws, 1);
        }
        computeChunk(i,cs,ws);
      }
    }

    private void computeChunk(int id, double [] cs, double [] ws){
      int [] nh = _nhs[id];
      int [] rs = _rss[id];
      Chunk resChk = _chks[id][_workIdx];
      int len = resChk._len;
      double [] ys;
      if(resChk instanceof C8DVolatileChunk){
        ys = ((C8DVolatileChunk)resChk).getValues();
      } else ys = resChk.getDoubles(_ys == null?MemoryManager.malloc8d(cs.length):_ys, 0, len);
      if(_weightIdx != -1) _chks[id][_weightIdx].getDoubles(ws, 0, len);
      final int hcslen = _lhcs.length;
      for (int c = _colFrom; c < _colTo; c++) {
        boolean extracted = false;
        for (int n = 0; n < hcslen; n++) {
          int sCols[] = _tree.undecided(n + _leaf)._scoreCols; // Columns to score (null, or a list of selected cols)
          if (sCols == null || ArrayUtils.find(sCols, c) >= 0) {
            if (!extracted) {
              _chks[id][c].getDoubles(cs,0,len);
              extracted = true;
            }
            DHistogram h = _lhcs[n][c - _colFrom];
            int hi = nh[n];
            int lo = (n == 0 ? 0 : nh[n - 1]);
            if (hi == lo || h == null) continue; // Ignore untracked columns in this split
            if (h._vals == null) h.init();
            h.updateHisto(ws, cs, ys, rs, hi, lo);
          }
        }
      }
    }

    @Override
    protected void reduce(ComputeHistoThread cc) {
      assert _lhcs != cc._lhcs;
      mergeHistos(_lhcs, cc._lhcs);
    }
  }

  @Override public void postGlobal(){
    for(DHistogram [] ary:_hcs)
      for(DHistogram dh:ary) {
        if(dh == null) continue;
        dh.reducePrecision();
      }
  }
}
