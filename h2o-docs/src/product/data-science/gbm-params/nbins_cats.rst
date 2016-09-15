``nbins_cats``
--------------

- Available in: GBM, DRF
- Hyperparameter: yes

Description
~~~~~~~~~~~

When training models with categorical columns (factors), the ``nbins_cats`` option specifies the number of `bins <../../glossary.html#bins>`__  to be included in the `histogram <../../glossary.html#histogram>`__ and then split at the best point. Because H2O does not perform `one-hot <https://en.wikipedia.org/wiki/One-hot>`__ encoding in the tree algorithms, we look at all the factor levels of a categorical predictor up to the resolution of the histogram, and then decide for each histogram bucket whether it goes left or right during splitting.

When the training data contains columns with categorical levels (factors), these factors are split by assigning an integer to each distinct categorical level, then binning the ordered integers according to the user-specified number of bins (which defaults to 1024 bins), and then picking the optimal split point among the bins. For example, if you have levels A,B,C,D,E,F,G at a certain node to be split, and you specify ``nbins_cats=4``, then the buckets {A,B},{C,D},{E,F},{G} define the grouping during the first split. Only during the next split of {A,B} (down the tree) will GBM separate {A} and {B}.

The value of ``nbins_cats`` for categorical factors has a much greater impact on the generalization error rate than ``nbins`` does for real- or integer-valued columns (where higher values mainly lead to more accurate numerical split points). For columns with many factors, a small ``nbins_cats`` value can add randomness to the split decisions (because the columns are grouped together somewhat arbitrarily), while large values (for example, values as large as the number of factor levels) can lead to perfect splits, resulting in `overfitting <https://en.m.wikipedia.org/wiki/Overfitting>`__ on the training set (AUC=1 in certain datasets). So this option is a very important tuning parameter that can make a big difference on the validation set accuracy. The default value for ``nbins_cats`` is 1024. Note that this default value can lead to large communication overhead for deep distributed tree models. ``nbins_cats`` can go up to 65k, which should be enough for most datasets.

To make a model more general, decrease ``nbins_top_level`` and ``nbins_cats``. To make a model more specific, increase ``nbins`` and/or ``nbins_top_level`` and ``nbins_cats``. Keep in mind that increasing ``nbins_cats`` can have a dramatic effect on the amount of overfitting.

**Note**: Currently in H2O, if the number of categorical values in a dataset exceeds the value specified with ``nbins_cats``, then the values are grouped into bins by `lexical ordering <https://en.wikipedia.org/wiki/Lexicographical_order>`__. 


Example
~~~~~~~



