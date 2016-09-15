``nbins``
---------

- Available in: GBM, DRF
- Hyperparameter: yes

Description
~~~~~~~~~~~

The ``nbins`` option specifies the number of bins to be included in the `histogram <../../glossary.html#histogram>`__ and then split at the best point. These split points are evaluated at the boundaries of each of these bins. 

Bins are linear sized from the observed min-to-max for the subset being split again (with an enforced large-nbins for shallow tree depths).  As the tree gets deeper, each subset (enforced by the tree decisions) covers a smaller range, and the bins are uniformly spread over this smaller range. Bin range decisions are thus made at each node level, not at the feature level.

This value defaults to 20 bins. If you have few observations in a node (but greater than 10), and ``nbins`` is set to 20 (the default), empty bins will be created if there aren't enough observations to go in each bin. As ``nbins`` goes up, the algorithm will more closely approximate evaluating each individual observation as a split point. To make a model more general, decrease ``nbins_top_level`` and ``nbins_cats``. To make a model more specific, increase ``nbins`` and/or ``nbins_top_level`` and ``nbins_cats``. Keep in mind that increasing ``nbins_cats`` can have a dramatic effect on the amount of overfitting.


Example
~~~~~~~

