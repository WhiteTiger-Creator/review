# Pack layout

Each .tlf blob starts with ASCII magic TLF1, then a little-endian site count.
Per site: id length, id bytes, two u16 side indexes, feature count, i16 feats,
hist width, and hist bytes used by the packing path. The feats array is the
enrollment-time feature vector used for half-open window selection.
