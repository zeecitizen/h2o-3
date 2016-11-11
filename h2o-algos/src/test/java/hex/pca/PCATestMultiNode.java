package hex.pca;

import org.junit.Assert;
import org.junit.BeforeClass;
import org.junit.Test;
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

      PCAModel.PCAParameters parms = new PCAModel.PCAParameters();
      parms._train = fr._key;
      parms._k = 4;
      parms._max_iterations = 1000;
      parms._pca_method = PCAModel.PCAParameters.Method.GLRM;
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
}
