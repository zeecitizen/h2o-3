from builtins import range
import sys, os
sys.path.insert(1, os.path.join("..",".."))
import h2o
from tests import pyunit_utils
from h2o.estimators.deeplearning import H2ODeepLearningEstimator

def tweedie_offset():

  insurance = h2o.import_file(pyunit_utils.locate("smalldata/glm_test/insurance.csv"))
  insurance["offset"] = insurance["Holders"].log()
  insurance["Group"] = insurance["Group"].asfactor()
  insurance["Age"] = insurance["Age"].asfactor()
  insurance["District"] = insurance["District"].asfactor()



  # without offset
  dl = H2ODeepLearningEstimator(distribution="tweedie",hidden=[1],epochs=1000,
                                train_samples_per_iteration=-1,reproducible=True,activation="Tanh",single_node_mode=False,
                                balance_classes=False,force_load_balance=False,seed=23123,tweedie_power=1.5,
                                score_training_samples=0,score_validation_samples=0)
  dl.train(x=list(range(3)),y="Claims", training_frame=insurance)
  mean_residual_deviance = dl.mean_residual_deviance()
  assert abs(0.61927 - mean_residual_deviance) < 1e-3, "Expected mean residual deviance to be 0.61927, but got " \
                                                     "{0}".format(mean_residual_deviance)
  predictions = dl.predict(insurance)
  assert abs(47.47-predictions[0].mean()[0]) < 1e-2, "Expected mean of predictions to be 47.47, but got " \
                                                  "{0}".format(predictions[0].mean()[0])
  assert abs(1.7157-predictions[0].min()) < 1e-1, "Expected min of predictions to be 1.7157, but got " \
                                                "{0}".format(predictions[0].min())
  assert abs(250.5-predictions[0].max()) < 28, "Expected max of predictions to be 250.5, but got " \
                                               "{0}".format(predictions[0].max())

  # with offset
  dl.train(x=list(range(3)),y="Claims", training_frame=insurance,offset_column="offset")
  mean_residual_deviance = dl.mean_residual_deviance()
  assert abs(0.2752-mean_residual_deviance) < 1e-2, "Expected mean residual deviance to be 0.2752, but got " \
                                                   "{0}".format(mean_residual_deviance)
  predictions = dl.predict(insurance)
  assert abs(49.657-predictions[0].mean()[0]) < 1e-1, "Expected mean of predictions to be 49.657, but got " \
                                                  "{0}".format(predictions[0].mean()[0])
  assert abs(1.074-predictions[0].min()) < 1e-1, "Expected min of predictions to be 1.074, but got " \
                                                 "{0}".format(predictions[0].min())
  assert abs(397.3-predictions[0].max()) < 40, "Expected max of predictions to be 397.3, but got " \
                                               "{0}".format(predictions[0].max())
if __name__ == "__main__":
  pyunit_utils.standalone_test(tweedie_offset)
else:
  tweedie_offset()