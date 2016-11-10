from __future__ import print_function
from builtins import str
from builtins import range
import sys
sys.path.insert(1,"../../../")
import h2o
from tests import pyunit_utils
from h2o.transforms.decomposition import H2OPCA

# This test is used to illustrate how to make PCA in multinode mode for now
# for Mark Chan.  Basically, you need to set pca_method = "GLRM" and
# set use_all_factor_levels = true.  However, with my one tiny machine, this
# runs rather slow.
#
# I will work on fixing the other modes while at least Mark can move forward.

def pca_arrests():
  print("Importing dataset 20000 rows by 400 columns ...")
  randomData = h2o.upload_file(pyunit_utils.locate("bigdata/laptop/jira/pca_pubdev_3672_400c_20000R.csv.zip"))
  randomData.describe()

  pca_k = 10
  print("H2O PCA with " + str(pca_k) + " dimensions:\n")
  pca_h2o = H2OPCA(k = pca_k, use_all_factor_levels=True, pca_method = "GLRM")
  pca_h2o.train(training_frame=randomData)
    # TODO: pca_h2o.show()


if __name__ == "__main__":
  pyunit_utils.standalone_test(pca_arrests)
else:
  pca_arrests()
