# Feature identity

Training discovers the union of feature names, sorts names by ascending UTF-8 byte sequence, and assigns indices from zero in that order. Prediction ignores names absent from the model.

Repeated feature names in a row are summed before prediction or gradient calculation. A feature whose accumulated value is zero remains represented but contributes zero. Model features are always serialized in ascending feature-name order.

This ordering is part of the reproducibility contract and must not depend on hash-map iteration order.
