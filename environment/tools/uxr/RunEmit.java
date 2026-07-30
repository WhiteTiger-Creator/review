package tools.uxr;

import java.nio.file.Path;
import java.util.List;
import v5.h8.HexEmit;
import v5.h8.RowDto;

final class RunEmit {
  static void go(Path out, List<RowDto> rows, long replaySeal, int epoch, Path side)
      throws Exception {
    new HexEmit().write(out, rows, replaySeal, epoch, side);
  }
}
