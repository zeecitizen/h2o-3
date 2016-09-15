``ntrees``
----------

- Available in: GBM, DRF
- Hyperparameter: yes

Description
~~~~~~~~~~~

For tree-based algorithms, this option specifies the number of trees to build in the model. In tree-based models, each node in the tree corresponds to a feature field from a dataset. Except for the top node, each node has an incoming branch. Similarly, except for the bottom node (or leaf node), each node has a number of outgoing branches. A branch represents a possible value for the input field from the originating dataset. A leaf represents the value of the objective field, given all the values for each input field in the chain of branches that go from the root (top) to that leaf.

This option defaults to 50 trees. 

Example
~~~~~~~