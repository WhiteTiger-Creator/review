package v5.h8;

/** One emitted sol_run row DTO. */
public final class RowDto {
  public final String rowId;
  public final String hopKey;
  public final long foldTag;
  public final long spanU64;
  public final String joinHex;
  public final String arm;
  public final int pad;

  public RowDto(
      String rowId,
      String hopKey,
      long foldTag,
      long spanU64,
      String joinHex,
      String arm,
      int pad) {
    this.rowId = rowId;
    this.hopKey = hopKey;
    this.foldTag = foldTag;
    this.spanU64 = spanU64;
    this.joinHex = joinHex;
    this.arm = arm;
    this.pad = pad;
  }
}
