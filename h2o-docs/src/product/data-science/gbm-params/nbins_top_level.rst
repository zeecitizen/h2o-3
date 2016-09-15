``nbins_top_level``
-------------------

- Available in: GBM, DRF
- Hyperparameter: yes

Description
~~~~~~~~~~~

For numerical columns (real/int), the ``nbins_top_level`` option is the number of bins to use at the top of each tree. It then divides by 2 at each ensuing level to find a new number. This option defaults to 1024 and is used with `nbins <nbins.html>`_, which controls when the algorithm stops dividing by 2.

To make a model more general, decrease ``nbins_top_level`` and ``nbins_cats``. To make a model more specific, increase ``nbins`` and/or ``nbins_top_level`` and ``nbins_cats``. Keep in mind that increasing ``nbins_cats`` can lead to in `overfitting <https://en.m.wikipedia.org/wiki/Overfitting>`__ on the training set.

Example
~~~~~~~

