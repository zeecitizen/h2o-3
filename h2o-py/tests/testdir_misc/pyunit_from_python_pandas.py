import sys
sys.path.insert(1,"../../")
import h2o
from tests import pyunit_utils
import pandas

def check_from_python_pandas():
    iris_wheader = pandas.read_csv(pyunit_utils.locate("smalldata/iris/iris_wheader.csv"))
    len_pd = len(iris_wheader)
    column_names_pd = list(iris_wheader.columns)

    #converting to an H2OFrame
    h2oframe = h2o.H2OFrame.from_python(iris_wheader)
    len_h2o = len(h2oframe)
    column_names_h2o = list(h2oframe.columns)

    assert len_pd == len_h2o, "Lengths of the dataframes in Pandas and H2O are mismatched"
    assert set(column_names_pd) == set(column_names_h2o), "Column names of the dataframes in Pandas and H2O are mismatched"

if __name__ == "__main__":
    pyunit_utils.standalone_test(check_from_python_pandas)
else:
    check_from_python_pandas()