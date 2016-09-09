``nbins_cats``
--------------

- Available in: GBM, DRF
- Hyperparameter: yes

Description
~~~~~~~~~~~

When training models with categorical columns (factors), the ``nbins_cats`` option specifies the number of `bins <../../glossary.html#bins>`__  to be included in the `histogram <../../glossary.html#histogram>`__ and then split at the best point. Because H2O does not perform `one-hot <https://en.wikipedia.org/wiki/One-hot>`__ encoding in the tree algorithms, we look at all the factor levels of a categorical predictor up to the resolution of the histogram, and then decide for each histogram bucket whether it goes left or right during splitting.

For example, if you have levels A,B,C,D,E,F,G at a certain node to be split, and you specify ``nbins_cats=4``, then the buckets {A,B},{C,D},{E,F},{G} define the grouping during the first split. Only during the next split of {A,B} (down the tree) will GBM separate {A} and {B}.

If ``nbins_cats`` = #factor levels, then you get “perfect” splits, resulting in total `overfitting <https://en.m.wikipedia.org/wiki/Overfitting>`__ on the training set (AUC=1 in certain datasets). So this option is a very important tuning parameter that can make a big difference on the validation set accuracy. 

The default for ``nbins_cats`` is 1024. Note that this default value can lead to large communication overhead for deep distributed tree models. ``nbins_cats`` can go up to 65k, which should be enough for most datasets.

**Note**: Currently in H2O, if the number of categorical values in a dataset exceeds the value specified with ``nbins_cats``, then the values are grouped into bins by lexical ordering.

Example
~~~~~~~



