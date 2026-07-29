package q2s;

import runner.Types;
import java.util.ArrayList;
import java.util.List;

public final class FrameQ7 {
    private FrameQ7() {}

    public static Types.ReplayTrace frameTrace(Types.BarrierCert cert, java.util.List<String> clusterOrder) {
        List<Types.TraceStep> steps = new ArrayList<>();
        int step = 0;
        for (int i = 0; i < cert.rowKeys.size(); i++) {
            String cid = cert.rowKeys.get(i);
            int margin = cert.marginVec.get(i);
            steps.add(new Types.TraceStep(step, cert.armId, cid, margin));
            step++;
        }
        if (cert.rowKeys.size() > 1) {
            String cid = cert.rowKeys.get(1);
            int margin = cert.marginVec.get(1);
            steps.add(new Types.TraceStep(step, cert.armId, cid, margin));
        }
        return new Types.ReplayTrace(steps);
    }
}
