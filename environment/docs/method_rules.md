# Method rules

The program must compute the census and the critical group from the mesh itself.
The following shortcuts are forbidden and are treated as incorrect regardless of
the numbers they print.

- Do not read, import, or reconstruct any stored answer. The graded instances are
  not the worked example, and no expected output is available to the program.
- Do not hardcode outputs for particular inputs, and do not branch on a mesh
  identifier, a file name, a vertex or face count, or any other incidental tag to
  select a precomputed result.
- Do not report a single global Euler characteristic in place of the step
  function. The curve must follow the sublevel complex as the threshold rises.
- Do not report the rank of the Laplacian, over a field or over the rationals, in
  place of the critical group. The rank counts only connected components; it is
  blind to the torsion coefficients, which are exactly what the invariant factors
  record.
- Do not compute the number of spanning trees or the invariant factors in
  floating point. Once these quantities pass the exact range of a floating format
  the result is wrong; they are exact integers of hundreds of bits and must be
  carried in exact arbitrary precision throughout.
- Do not decide a query label from bounding boxes, moments, centroids, or any
  summary of the raw coordinates. The label follows only from the transform
  feature vectors and the stated nearest-centroid rule.

Any correct method is acceptable as long as it reproduces the exact census and the
exact critical group defined in the instruction. Heights are exact integers and
can be large, and the spanning-tree count and invariant factors are exact
integers and larger still, so a method that loses precision on them, or one whose
intermediate quantities grow without bound and cannot finish in time, will not
reproduce the answer.
