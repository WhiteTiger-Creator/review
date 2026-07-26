package runner;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class Types {
    private Types() {}

    public static final class ClusterRec {
        public final String clusterId;
        public final String cueBytes;
        public final boolean boundary;
        public final String neighborId;

        public ClusterRec(String clusterId, String cueBytes, boolean boundary, String neighborId) {
            this.clusterId = clusterId;
            this.cueBytes = cueBytes;
            this.boundary = boundary;
            this.neighborId = neighborId;
        }
    }

    public static final class PackDoc {
        public final int caseId;
        public final int armId;
        public final List<ClusterRec> clusters;
        public final Map<String, String> labelMap;
        public final List<String> permuteOrder;
        public final List<Integer> marginBases;

        public PackDoc(int caseId, int armId, List<ClusterRec> clusters, Map<String, String> labelMap,
                List<String> permuteOrder, List<Integer> marginBases) {
            this.caseId = caseId;
            this.armId = armId;
            this.clusters = clusters;
            this.labelMap = labelMap;
            this.permuteOrder = permuteOrder;
            this.marginBases = marginBases;
        }
    }

    public static final class AnnexCtx {
        public final PackDoc pack;
        public final boolean applyPermute;

        public AnnexCtx(PackDoc pack, boolean applyPermute) {
            this.pack = pack;
            this.applyPermute = applyPermute;
        }
    }

    public static final class LatticeView {
        public final Map<String, String> narrowed;
        public final int armId;

        public LatticeView(Map<String, String> narrowed, int armId) {
            this.narrowed = narrowed;
            this.armId = armId;
        }
    }

    public static final class BarrierTable {
        public final List<String> rowKeys;
        public final List<Integer> bases;
        public final List<Integer> cueHashes;

        public BarrierTable(List<String> rowKeys, List<Integer> bases, List<Integer> cueHashes) {
            this.rowKeys = rowKeys;
            this.bases = bases;
            this.cueHashes = cueHashes;
        }
    }

    public static final class DrawRec {
        public final String wave;
        public final int armId;
        public final String clusterId;
        public final double weight;

        public DrawRec(String wave, int armId, String clusterId, double weight) {
            this.wave = wave;
            this.armId = armId;
            this.clusterId = clusterId;
            this.weight = weight;
        }
    }

    public static final class DrawSet {
        public final String wave;
        public final List<DrawRec> draws;
        public final double terminationWeight;

        public DrawSet(String wave, List<DrawRec> draws, double terminationWeight) {
            this.wave = wave;
            this.draws = draws;
            this.terminationWeight = terminationWeight;
        }
    }

    public static final class BarrierCert {
        public final List<Integer> marginVec;
        public final List<String> rowKeys;
        public final int armId;

        public BarrierCert(List<Integer> marginVec, List<String> rowKeys, int armId) {
            this.marginVec = marginVec;
            this.rowKeys = rowKeys;
            this.armId = armId;
        }
    }

    public static final class TraceStep {
        public final int step;
        public final int armId;
        public final String clusterId;
        public final int margin;

        public TraceStep(int step, int armId, String clusterId, int margin) {
            this.step = step;
            this.armId = armId;
            this.clusterId = clusterId;
            this.margin = margin;
        }
    }

    public static final class ReplayTrace {
        public final List<TraceStep> steps;

        public ReplayTrace(List<TraceStep> steps) {
            this.steps = steps;
        }
    }

    public static final class WitnessRow {
        public final int armId;
        public final String clusterId;
        public final int margin;
        public final String ref;

        public WitnessRow(int armId, String clusterId, int margin, String ref) {
            this.armId = armId;
            this.clusterId = clusterId;
            this.margin = margin;
            this.ref = ref;
        }
    }

    public static final class DeltaRow {
        public final int step;
        public final int armId;
        public final String clusterId;
        public final int delta;

        public DeltaRow(int step, int armId, String clusterId, int delta) {
            this.step = step;
            this.armId = armId;
            this.clusterId = clusterId;
            this.delta = delta;
        }
    }

    public static final class ReportDoc {
        public int caseId;
        public String runMode;
        public List<WitnessRow> witnessRows = new ArrayList<>();
        public List<Integer> barrierMargins = new ArrayList<>();
        public List<DeltaRow> replayDeltas = new ArrayList<>();
        public String mergeToken = "";
    }
}
