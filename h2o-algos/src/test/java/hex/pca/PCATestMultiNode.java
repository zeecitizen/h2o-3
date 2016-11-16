package hex.pca;

import hex.DataInfo;
import hex.SplitFrame;
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


  // quick fix for MarkC here.  Use GLRM for PCA for now since I fixed it already.
  @Test
  public void testMultiNodePCAGLRM() throws InterruptedException, ExecutionException {
    PCAModel model = null;
    Frame fr = null, fr2= null;

    try {
      fr = parse_test_file(Key.make("SDSS_quasar.hex"), "smalldata/pca_test/SDSS_quasar.txt.zip");
//      fr = parse_test_file(Key.make("SDSS_quasar.hex"), "bigdata/laptop/jira/pca_pubdev_3672_400c_20000R.csv.zip");
      PCAModel.PCAParameters parms = new PCAModel.PCAParameters();
      parms._train = fr._key;
      parms._k = 4;
      parms._max_iterations = 1000;
      parms._pca_method = PCAModel.PCAParameters.Method.Randomized;
      parms._use_all_factor_levels = true;

      model = new PCA(parms).trainModel().get();

      // Done building model; produce a score column with cluster choices
      fr2 = model.score(fr);
      Assert.assertTrue(model.testJavaScoring(fr, fr2, 1e-5));
    } finally {
      if( fr  != null ) fr.delete();
      if( fr2 != null ) fr2.delete();
      if (model != null) model.delete();
    }
  }

  @Test
  public void testMultiNodeErinPCA() throws InterruptedException, ExecutionException {
    PCAModel model = null;
    Frame fr = null, fr2= null;
    Frame tr = null, te= null;

    try {
      fr = parse_test_file("bigdata/laptop/jira/rotterdam.csv.zip");
      SplitFrame sf = new SplitFrame(fr,new double[] { 0.5, 0.5 },new Key[] { Key.make("train.hex"), Key.make("test.hex")});

      // Invoke the job
      sf.exec().get();
      Key[] ksplits = sf._destination_frames;
      tr = DKV.get(ksplits[0]).get();
      te = DKV.get(ksplits[1]).get();

      PCAModel.PCAParameters parms = new PCAModel.PCAParameters();
      parms._train = ksplits[0];
      parms._valid = ksplits[1];
      parms._k = 8;
      parms._max_iterations = 1000;
      parms._pca_method = PCAModel.PCAParameters.Method.GramSVD;

      model = new PCA(parms).trainModel().get();  // Erin: does not work.  Arghhh!

      // Done building model; produce a score column with cluster choices
      fr2 = model.score(te);
      Assert.assertTrue(model.testJavaScoring(te, fr2, 1e-5));

      // try with Power method
      parms._pca_method = PCAModel.PCAParameters.Method.Power;
      parms._k = 20;
      parms._transform = DataInfo.TransformType.STANDARDIZE;
      parms._use_all_factor_levels = true;

      model = new PCA(parms).trainModel().get();  // Erin: There is error in thbis one.  Arghhh!
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
