package water.rapids.ast.prims.advmath;

import water.MRTask;
import water.fvec.Chunk;
import water.fvec.Frame;
import water.fvec.NewChunk;
import water.fvec.Vec;
import water.rapids.Env;
import water.rapids.Val;
import water.rapids.ast.AstPrimitive;
import water.rapids.ast.AstRoot;
import water.rapids.ast.params.AstNum;
import water.rapids.ast.params.AstNumList;
import water.rapids.ast.params.AstStr;
import water.rapids.vals.ValFrame;
import water.util.ArrayUtils;

import java.util.ArrayList;


public class AstISax extends AstPrimitive {
  @Override
  public String[] args() { return new String[]{"ary", "numWords", "maxCardinality"}; }

  @Override
  public int nargs() { return 1 + 3; } // (isax x breaks)

  @Override
  public String str() { return "isax"; }

  @Override
  public Val apply(Env env, Env.StackHelp stk, AstRoot asts[]) {
    // stack is [ ..., ary, numWords, maxCardinality]
    // handle the breaks
    Frame fr2;
    Frame f = stk.track(asts[1].exec(env)).getFrame();

    //delete me
    Vec vec = f.anyVec();

    int c = 0;
    for (Vec v : f.vecs()) {
      if (!v.isNumeric()) c++;
    }
    if (c > 0) throw new IllegalArgumentException("iSAX only applies to numeric columns");

    // delete this block
    AstRoot a = asts[2];
    String algo = null;
    int numBreaks = -1;
    double[] breaks = null;

    AstRoot n = asts[2];
    AstRoot mc = asts[3];
    int numWords = -1;
    int maxCardinality = -1;

    numWords = (int) n.exec(env).getNum();
    maxCardinality = (int) mc.exec(env).getNum();

    // delete this block
    if (a instanceof AstStr) algo = a.str().toLowerCase();
    else if (a instanceof AstNumList) breaks = ((AstNumList) a).expand();
    else if (a instanceof AstNum) numBreaks = (int) a.exec(env).getNum();

    double globalMax = 0;
    double globalMin = 0;

    for (Vec v : f.vecs()) {
      double vmax = v.max();
      double vmin = v.min();
      if (vmax > globalMax) globalMax = vmax;
      if (vmin < globalMin) globalMin = vmin;
    }
    AstISax.ISaxTask isaxt;
    double h;
    double x1 = vec.max();
    double x0 = vec.min();

    ArrayList<String> columns = new ArrayList<String>();
    for (int i = 0; i < numWords; i++) {
      columns.add("c"+i);
    }
    fr2 = new AstISax.ISaxTask(numWords, maxCardinality, globalMax, globalMin)
            .doAll(numWords, Vec.T_NUM, f).outputFrame(null, columns.toArray(new String[numWords]), null);

    return new ValFrame(fr2);
  }


  public static class ISaxTask extends MRTask<AstISax.ISaxTask> {
    public int nw;
    public int mc;
    public double gMax;
    public double gMin;
    ISaxTask(int numWords, int maxCardinality, double globalMax, double globalMin) {
      nw = numWords;
      mc = maxCardinality;
      gMax = globalMax;
      gMin = globalMin;
    }
    @Override
    public void map(Chunk cs[],NewChunk[] nc) {
      int step = cs.length/nw;
      int chunkSize = cs[0].len();
      int icnt = 0;
      for (int i = 0; i < cs.length; i+=step) {
        Chunk subset[] = ArrayUtils.subarray(cs,i,i+step);
        for (int j = 0; j < chunkSize; j++) {
          double mySum = 0.0;
          double myCount = 0.0;
          for (Chunk c : subset) {
            if (c != null) {
              mySum += c.atd(j);
              myCount++;
            }
          }
          double chunkMean = mySum / myCount;
          nc[icnt].addNum(chunkMean);
        }
        icnt++;
        if (icnt == nw) break;
      }
      System.out.print("map ISAX");
    }
  }


}
