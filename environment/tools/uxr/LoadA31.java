package tools.uxr;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import r4.n2.SlotView;

/** Loads packed blob and shard overlays. */
public final class LoadA31 {
  public int magic(Path root) throws Exception {
    Path blob = root.resolve("slot_blob.bin");
    byte[] raw = Files.readAllBytes(blob);
    ByteBuffer bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
    return bb.getInt();
  }

  public SlotView load(Path root) throws Exception {
    Path blob = root.resolve("slot_blob.bin");
    byte[] raw = Files.readAllBytes(blob);
    ByteBuffer bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
    int magic = bb.getInt();
    if (magic != 0xA31C0FFE) {
      throw new IllegalStateException("bad magic");
    }
    int count = bb.getInt();
    List<SlotView.Slot> slots = new ArrayList<>();
    for (int i = 0; i < count; i++) {
      int idLen = bb.getShort() & 0xffff;
      byte[] idb = new byte[idLen];
      bb.get(idb);
      String id = new String(idb, java.nio.charset.StandardCharsets.UTF_8);
      int pad = bb.get() & 0xff;
      int arm = bb.get() & 0xff;
      int slotIx = bb.getInt();
      int lo = bb.getInt();
      int hi = bb.getInt();
      int w = bb.getInt();
      slots.add(new SlotView.Slot(id, pad, arm, lo, hi, w));
      if (slotIx < 0) {
        throw new IllegalStateException("slot");
      }
    }
    return new SlotView(slots);
  }
}
