package hex.pca;

import hex.SplitFrame;
import hex.pca.PCAModel.PCAParameters;
import org.junit.Assert;
import org.junit.BeforeClass;
import org.junit.Test;
import water.DKV;
import water.Key;
import water.TestUtil;
import water.fvec.Frame;

import java.util.concurrent.ExecutionException;

public class PCATestMultiNode extends TestUtil {
  public static final double TOLERANCE = 1e-6;
  @BeforeClass public static void setup() { stall_till_cloudsize(1); }


  @Test public void testMultiNodePCA() throws InterruptedException, ExecutionException {
    PCAModel model = null;
    Frame fr = null, fr2= null;
    Frame tr = null, te= null;

    try {
      fr = parse_test_file("smalldata/pca_test/pca_400c_20000R.csv");
      SplitFrame sf = new SplitFrame(fr,new double[] { 0.9, 0.1 },new Key[] { Key.make("train.hex"), Key.make("test.hex")});

      // Invoke the job
      sf.exec().get();
      Key[] ksplits = sf._destination_frames;
      tr = DKV.get(ksplits[0]).get();
      te = DKV.get(ksplits[1]).get();

      PCAModel.PCAParameters parms = new PCAModel.PCAParameters();
      parms._train = ksplits[0];
      parms._valid = ksplits[1];
      parms._k = 4;
      parms._max_iterations = 1000;
      parms._pca_method = PCAParameters.Method.GramSVD;

      model = new PCA(parms).trainModel().get();

      // Done building model; produce a score column with cluster choices
      fr2 = model.score(te);
      Assert.assertTrue(model.testJavaScoring(te, fr2, 1e-5));
    } finally {
      if( fr  != null ) fr.delete();
      if( fr2 != null ) fr2.delete();
      if( tr  != null ) tr .delete();
      if( te  != null ) te .delete();
      if (model != null) model.delete();
    }
  }
}
