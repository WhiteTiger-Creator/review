using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

public static class Program
{
    static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
    static readonly string[] Reports = {
        "cell_flux.csv",
        "ring_summary.csv",
        "mode_coupling.csv",
        "region_balance.json",
        "gradient_audit.csv",
        "latitude_frontier.csv",
        "mode_spectrum.csv",
        "ring_mode_breakdown.csv"
    };

    public static int Main(string[] args)
    {
        string inputDir;
        string outputDir;
        if (args.Length == 0)
        {
            inputDir = "/app/task_file/input";
            outputDir = "/app/task_file/output";
        }
        else if (args.Length == 2)
        {
            inputDir = args[0];
            outputDir = args[1];
        }
        else
        {
            Console.Error.WriteLine("usage: mono sphere-flux.exe [input_dir output_dir]");
            return 2;
        }

        try
        {
            Data data = Parse(inputDir);
            Dictionary<string, string> reports = Render(data);
            Directory.CreateDirectory(outputDir);
            foreach (string report in Reports)
            {
                File.WriteAllText(Path.Combine(outputDir, report), reports[report], new UTF8Encoding(false));
            }
            return 0;
        }
        catch (Exception ex)
        {
            DeleteOutput(outputDir);
            Console.Error.WriteLine(ex.Message);
            return 1;
        }
    }

    static void DeleteOutput(string outputDir)
    {
        try
        {
            if (Directory.Exists(outputDir))
            {
                Directory.Delete(outputDir, true);
            }
            else if (File.Exists(outputDir))
            {
                File.Delete(outputDir);
            }
        }
        catch
        {
            // Best-effort cleanup for malformed inputs.
        }
    }

    sealed class Settings
    {
        public int QuadratureOrder;
        public double RotationRadians;
        public double ClipFloor;
        public double AlertFlux;
    }

    sealed class Ring
    {
        public string Id = "";
        public double ThetaMin;
        public double ThetaMax;
        public int Order;
    }

    sealed class Cell
    {
        public string Id = "";
        public Ring Ring = new Ring();
        public string Region = "";
        public double PhiStart;
        public double PhiEnd;
        public double Exposure;
        public int Order;
        public List<PhiSegment> Segments = new List<PhiSegment>();
    }

    sealed class PhiSegment
    {
        public double A;
        public double B;

        public PhiSegment(double a, double b)
        {
            A = a;
            B = b;
        }
    }

    sealed class Mode
    {
        public string Id = "";
        public int Ell;
        public int M;
        public char Kind;
        public double Coefficient;
        public int Order;
    }

    sealed class Data
    {
        public Settings Settings = new Settings();
        public List<Ring> Rings = new List<Ring>();
        public List<Cell> Cells = new List<Cell>();
        public List<Mode> Modes = new List<Mode>();
        public double[] Nodes = new double[0];
        public double[] Weights = new double[0];
    }

    sealed class CellResult
    {
        public Cell Cell;
        public double Area;
        public double RawFlux;
        public double ClippedFlux;
        public double MeanRaw;
        public double MeanClipped;
        public int ClippedNodes;
        public double[] ModeContrib;
        public double ThetaEnergy;
        public double PhiEnergy;
        public double[] GradientModeContrib;
        public double[,] Coupling;
        public double[,] WeightedCoupling;

        public CellResult(Cell cell, int modeCount)
        {
            Cell = cell;
            ModeContrib = new double[modeCount];
            GradientModeContrib = new double[modeCount];
            Coupling = new double[modeCount, modeCount];
            WeightedCoupling = new double[modeCount, modeCount];
        }
    }

    sealed class RegionAccum
    {
        public int CellCount;
        public double Area;
        public double RawFlux;
        public double ClippedFlux;
        public double[] ModeContrib;
        public double[,] Coupling;
        public double[,] WeightedCoupling;

        public RegionAccum(int modeCount)
        {
            ModeContrib = new double[modeCount];
            Coupling = new double[modeCount, modeCount];
            WeightedCoupling = new double[modeCount, modeCount];
        }
    }

    static Data Parse(string inputDir)
    {
        Data data = new Data();
        data.Settings = ParseSettings(Path.Combine(inputDir, "settings.csv"));
        data.Rings = ParseRings(Path.Combine(inputDir, "rings.csv"));
        Dictionary<string, Ring> ringById = new Dictionary<string, Ring>(StringComparer.Ordinal);
        foreach (Ring ring in data.Rings)
        {
            ringById.Add(ring.Id, ring);
        }
        data.Cells = ParseCells(Path.Combine(inputDir, "cells.csv"), ringById);
        data.Modes = ParseModes(Path.Combine(inputDir, "modes.csv"));
        if (data.Modes.Count == 0)
        {
            throw new Exception("missing modes");
        }
        GaussLegendre(data.Settings.QuadratureOrder, out data.Nodes, out data.Weights);
        return data;
    }

    static Settings ParseSettings(string path)
    {
        List<string[]> rows = ReadCsv(path, new[] { "key", "value" });
        Dictionary<string, string> values = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (string[] row in rows)
        {
            if (values.ContainsKey(row[0]))
            {
                throw new Exception("duplicate setting");
            }
            values[row[0]] = row[1];
        }
        string[] required = { "quadrature_order", "rotation_degrees", "clip_floor", "alert_flux" };
        foreach (string key in required)
        {
            if (!values.ContainsKey(key))
            {
                throw new Exception("missing setting");
            }
        }
        if (values.Count != required.Length)
        {
            throw new Exception("extra setting");
        }
        int order = ParseInt(values["quadrature_order"]);
        if (order < 4 || order > 24)
        {
            throw new Exception("bad quadrature order");
        }
        Settings settings = new Settings();
        settings.QuadratureOrder = order;
        settings.RotationRadians = ParseDouble(values["rotation_degrees"]) * Math.PI / 180.0;
        settings.ClipFloor = ParseDouble(values["clip_floor"]);
        settings.AlertFlux = ParseDouble(values["alert_flux"]);
        return settings;
    }

    static List<Ring> ParseRings(string path)
    {
        List<string[]> rows = ReadCsv(path, new[] { "ring_id", "theta_min_deg", "theta_max_deg" });
        List<Ring> rings = new List<Ring>();
        HashSet<string> ids = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < rows.Count; i++)
        {
            string id = Token(rows[i][0]);
            if (!ids.Add(id))
            {
                throw new Exception("duplicate ring");
            }
            double a = ParseDouble(rows[i][1]);
            double b = ParseDouble(rows[i][2]);
            if (!(0.0 <= a && a < b && b <= 180.0))
            {
                throw new Exception("bad ring theta");
            }
            rings.Add(new Ring { Id = id, ThetaMin = a, ThetaMax = b, Order = i });
        }
        if (rings.Count == 0)
        {
            throw new Exception("missing rings");
        }
        return rings;
    }

    static List<Cell> ParseCells(string path, Dictionary<string, Ring> ringById)
    {
        List<string[]> rows = ReadCsv(path, new[] { "cell_id", "ring_id", "phi_start_deg", "phi_end_deg", "region", "exposure" });
        List<Cell> cells = new List<Cell>();
        HashSet<string> ids = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < rows.Count; i++)
        {
            string id = Token(rows[i][0]);
            string ringId = Token(rows[i][1]);
            string region = Token(rows[i][4]);
            if (!ids.Add(id))
            {
                throw new Exception("duplicate cell");
            }
            if (!ringById.ContainsKey(ringId))
            {
                throw new Exception("unknown ring");
            }
            double start = ParseDouble(rows[i][2]);
            double end = ParseDouble(rows[i][3]);
            double exposure = ParseDouble(rows[i][5]);
            double width = end - start;
            if (!(width > 0.0 && width <= 360.0) || !(exposure > 0.0))
            {
                throw new Exception("bad cell");
            }
            Cell cell = new Cell
            {
                Id = id,
                Ring = ringById[ringId],
                Region = region,
                PhiStart = start,
                PhiEnd = end,
                Exposure = exposure,
                Order = i,
                Segments = NormalizePhi(start, end)
            };
            cells.Add(cell);
        }
        if (cells.Count == 0)
        {
            throw new Exception("missing cells");
        }
        return cells;
    }

    static List<Mode> ParseModes(string path)
    {
        List<string[]> rows = ReadCsv(path, new[] { "mode_id", "ell", "m", "kind", "coefficient" });
        List<Mode> modes = new List<Mode>();
        HashSet<string> ids = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < rows.Count; i++)
        {
            string id = Token(rows[i][0]);
            if (!ids.Add(id))
            {
                throw new Exception("duplicate mode");
            }
            int ell = ParseInt(rows[i][1]);
            int m = ParseInt(rows[i][2]);
            string kindText = rows[i][3];
            if (kindText.Length != 1 || (kindText[0] != 'C' && kindText[0] != 'S'))
            {
                throw new Exception("bad mode kind");
            }
            if (ell < 0 || m < 0 || m > ell || (kindText[0] == 'S' && m == 0))
            {
                throw new Exception("bad mode index");
            }
            modes.Add(new Mode
            {
                Id = id,
                Ell = ell,
                M = m,
                Kind = kindText[0],
                Coefficient = ParseDouble(rows[i][4]),
                Order = i
            });
        }
        return modes;
    }

    static Dictionary<string, string> Render(Data data)
    {
        List<CellResult> cellResults = new List<CellResult>();
        Dictionary<string, RegionAccum> regions = new Dictionary<string, RegionAccum>(StringComparer.Ordinal);
        foreach (Cell cell in data.Cells)
        {
            CellResult result = IntegrateCell(data, cell, cell.Ring.ThetaMin, cell.Ring.ThetaMax, true);
            cellResults.Add(result);
            if (!regions.ContainsKey(cell.Region))
            {
                regions[cell.Region] = new RegionAccum(data.Modes.Count);
            }
            AddRegion(regions[cell.Region], result);
        }

        Dictionary<string, string> output = new Dictionary<string, string>(StringComparer.Ordinal);
        output["cell_flux.csv"] = RenderCellFlux(data, cellResults);
        output["ring_summary.csv"] = RenderRingSummary(data, cellResults);
        output["mode_coupling.csv"] = RenderModeCoupling(data, regions);
        output["region_balance.json"] = RenderRegionBalance(data, regions);
        output["gradient_audit.csv"] = RenderGradientAudit(data, cellResults);
        output["latitude_frontier.csv"] = RenderLatitudeFrontier(data);
        output["mode_spectrum.csv"] = RenderModeSpectrum(data, cellResults);
        output["ring_mode_breakdown.csv"] = RenderRingModeBreakdown(data, cellResults);
        return output;
    }

    static void AddRegion(RegionAccum accum, CellResult result)
    {
        int n = result.ModeContrib.Length;
        accum.CellCount++;
        accum.Area += result.Area;
        accum.RawFlux += result.RawFlux;
        accum.ClippedFlux += result.ClippedFlux;
        for (int i = 0; i < n; i++)
        {
            accum.ModeContrib[i] += result.ModeContrib[i];
            for (int j = 0; j < n; j++)
            {
                accum.Coupling[i, j] += result.Coupling[i, j];
                accum.WeightedCoupling[i, j] += result.WeightedCoupling[i, j];
            }
        }
    }

    static string RenderCellFlux(Data data, List<CellResult> results)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("cell_id,ring_id,region,area,raw_flux,clipped_flux,mean_raw,mean_clipped,clipped_nodes,dominant_mode");
        foreach (CellResult result in results.OrderBy(r => r.Cell.Order))
        {
            sb.Append(result.Cell.Id).Append(',')
              .Append(result.Cell.Ring.Id).Append(',')
              .Append(result.Cell.Region).Append(',')
              .Append(F(result.Area)).Append(',')
              .Append(F(result.RawFlux)).Append(',')
              .Append(F(result.ClippedFlux)).Append(',')
              .Append(F(result.MeanRaw)).Append(',')
              .Append(F(result.MeanClipped)).Append(',')
              .Append(result.ClippedNodes.ToString(Inv)).Append(',')
              .Append(DominantMode(data, result.ModeContrib))
              .Append('\n');
        }
        return sb.ToString();
    }

    static string RenderRingSummary(Data data, List<CellResult> results)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("ring_id,cell_count,total_area,total_raw_flux,total_clipped_flux,clip_delta,max_mean_cell,alert_count,regions");
        foreach (Ring ring in data.Rings.OrderBy(r => r.Order))
        {
            List<CellResult> group = results.Where(r => Object.ReferenceEquals(r.Cell.Ring, ring)).OrderBy(r => r.Cell.Order).ToList();
            double area = group.Sum(r => r.Area);
            double raw = group.Sum(r => r.RawFlux);
            double clipped = group.Sum(r => r.ClippedFlux);
            string maxCell = "";
            if (group.Count > 0)
            {
                double best = group[0].MeanClipped;
                maxCell = group[0].Cell.Id;
                int bestOrder = group[0].Cell.Order;
                foreach (CellResult candidate in group)
                {
                    if (candidate.MeanClipped > best || (candidate.MeanClipped == best && candidate.Cell.Order < bestOrder))
                    {
                        best = candidate.MeanClipped;
                        bestOrder = candidate.Cell.Order;
                        maxCell = candidate.Cell.Id;
                    }
                }
            }
            int alerts = group.Count(r => r.ClippedFlux >= data.Settings.AlertFlux);
            SortedDictionary<string, int> regionCounts = new SortedDictionary<string, int>(StringComparer.Ordinal);
            foreach (CellResult result in group)
            {
                if (!regionCounts.ContainsKey(result.Cell.Region))
                {
                    regionCounts[result.Cell.Region] = 0;
                }
                regionCounts[result.Cell.Region]++;
            }
            string regionText = String.Join(";", regionCounts.Select(kv => kv.Key + ":" + kv.Value.ToString(Inv)).ToArray());
            sb.Append(ring.Id).Append(',')
              .Append(group.Count.ToString(Inv)).Append(',')
              .Append(F(area)).Append(',')
              .Append(F(raw)).Append(',')
              .Append(F(clipped)).Append(',')
              .Append(F(clipped - raw)).Append(',')
              .Append(maxCell).Append(',')
              .Append(alerts.ToString(Inv)).Append(',')
              .Append(regionText).Append('\n');
        }
        return sb.ToString();
    }

    static string RenderModeCoupling(Data data, Dictionary<string, RegionAccum> regions)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("region,mode_a,mode_b,coupling,weighted_coupling,correlation");
        int n = data.Modes.Count;
        foreach (string region in regions.Keys.OrderBy(x => x, StringComparer.Ordinal))
        {
            RegionAccum accum = regions[region];
            for (int i = 0; i < n; i++)
            {
                for (int j = i; j < n; j++)
                {
                    double denom = Math.Sqrt(Math.Abs(accum.WeightedCoupling[i, i] * accum.WeightedCoupling[j, j]));
                    double corr = denom == 0.0 ? 0.0 : accum.WeightedCoupling[i, j] / denom;
                    sb.Append(region).Append(',')
                      .Append(data.Modes[i].Id).Append(',')
                      .Append(data.Modes[j].Id).Append(',')
                      .Append(F(accum.Coupling[i, j])).Append(',')
                      .Append(F(accum.WeightedCoupling[i, j])).Append(',')
                      .Append(F(corr)).Append('\n');
                }
            }
        }
        return sb.ToString();
    }

    static string RenderRegionBalance(Data data, Dictionary<string, RegionAccum> regions)
    {
        double totalArea = 0.0;
        double totalRaw = 0.0;
        double totalClipped = 0.0;
        foreach (RegionAccum accum in regions.Values)
        {
            totalArea += accum.Area;
            totalRaw += accum.RawFlux;
            totalClipped += accum.ClippedFlux;
        }
        StringBuilder sb = new StringBuilder();
        sb.Append('{')
          .Append("\"total_area\":").Append(F(totalArea)).Append(',')
          .Append("\"total_raw_flux\":").Append(F(totalRaw)).Append(',')
          .Append("\"total_clipped_flux\":").Append(F(totalClipped)).Append(',')
          .Append("\"clip_delta\":").Append(F(totalClipped - totalRaw)).Append(',')
          .Append("\"regions\":[");
        bool first = true;
        foreach (string region in regions.Keys.OrderBy(x => x, StringComparer.Ordinal))
        {
            if (!first)
            {
                sb.Append(',');
            }
            first = false;
            RegionAccum accum = regions[region];
            sb.Append('{')
              .Append("\"region\":\"").Append(JsonEscape(region)).Append("\",")
              .Append("\"cell_count\":").Append(accum.CellCount.ToString(Inv)).Append(',')
              .Append("\"area\":").Append(F(accum.Area)).Append(',')
              .Append("\"raw_flux\":").Append(F(accum.RawFlux)).Append(',')
              .Append("\"clipped_flux\":").Append(F(accum.ClippedFlux)).Append(',')
              .Append("\"clip_delta\":").Append(F(accum.ClippedFlux - accum.RawFlux)).Append(',')
              .Append("\"dominant_mode\":\"").Append(JsonEscape(DominantMode(data, accum.ModeContrib))).Append("\"")
              .Append('}');
        }
        sb.Append("]}\n");
        return sb.ToString();
    }

    static string RenderGradientAudit(Data data, List<CellResult> results)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("cell_id,region,theta_energy,phi_energy,total_gradient_energy,anisotropy,dominant_gradient_mode");
        foreach (CellResult result in results.OrderBy(r => r.Cell.Order))
        {
            double total = result.ThetaEnergy + result.PhiEnergy;
            double anisotropy = total == 0.0 ? 0.0 : result.PhiEnergy / total;
            sb.Append(result.Cell.Id).Append(',')
              .Append(result.Cell.Region).Append(',')
              .Append(F(result.ThetaEnergy)).Append(',')
              .Append(F(result.PhiEnergy)).Append(',')
              .Append(F(total)).Append(',')
              .Append(F(anisotropy)).Append(',')
              .Append(DominantMode(data, result.GradientModeContrib))
              .Append('\n');
        }
        return sb.ToString();
    }

    static string RenderLatitudeFrontier(Data data)
    {
        SortedSet<double> faces = new SortedSet<double>();
        foreach (Ring ring in data.Rings)
        {
            faces.Add(ring.ThetaMin);
            faces.Add(ring.ThetaMax);
        }
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("face,theta_deg,area_left,raw_flux_left,clipped_flux_left,clip_delta_left,active_cells");
        int face = 0;
        foreach (double theta in faces)
        {
            double area = 0.0;
            double raw = 0.0;
            double clipped = 0.0;
            int active = 0;
            foreach (Cell cell in data.Cells)
            {
                double a = cell.Ring.ThetaMin;
                double b = Math.Min(theta, cell.Ring.ThetaMax);
                if (b > a)
                {
                    active++;
                    CellResult partial = IntegrateCell(data, cell, a, b, false);
                    area += partial.Area;
                    raw += partial.RawFlux;
                    clipped += partial.ClippedFlux;
                }
            }
            sb.Append(face.ToString(Inv)).Append(',')
              .Append(F(theta)).Append(',')
              .Append(F(area)).Append(',')
              .Append(F(raw)).Append(',')
              .Append(F(clipped)).Append(',')
              .Append(F(clipped - raw)).Append(',')
              .Append(active.ToString(Inv)).Append('\n');
            face++;
        }
        return sb.ToString();
    }

    static string RenderModeSpectrum(Data data, List<CellResult> results)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("mode_id,total_raw_contribution,positive_cells,negative_cells,dominant_cell,gradient_energy,gradient_share");
        int n = data.Modes.Count;
        double[] gradientTotals = new double[n];
        for (int i = 0; i < n; i++)
        {
            gradientTotals[i] = results.Sum(r => r.GradientModeContrib[i]);
        }
        double allGradient = gradientTotals.Sum();
        for (int i = 0; i < n; i++)
        {
            double raw = 0.0;
            int positive = 0;
            int negative = 0;
            string dominantCell = "";
            double dominantAbs = -1.0;
            int dominantOrder = Int32.MaxValue;
            foreach (CellResult result in results.OrderBy(r => r.Cell.Order))
            {
                double value = result.ModeContrib[i];
                raw += value;
                if (value > 0.0)
                {
                    positive++;
                }
                else if (value < 0.0)
                {
                    negative++;
                }
                double abs = Math.Abs(value);
                if (abs > dominantAbs || (abs == dominantAbs && result.Cell.Order < dominantOrder))
                {
                    dominantAbs = abs;
                    dominantOrder = result.Cell.Order;
                    dominantCell = result.Cell.Id;
                }
            }
            double share = allGradient == 0.0 ? 0.0 : gradientTotals[i] / allGradient;
            sb.Append(data.Modes[i].Id).Append(',')
              .Append(F(raw)).Append(',')
              .Append(positive.ToString(Inv)).Append(',')
              .Append(negative.ToString(Inv)).Append(',')
              .Append(dominantCell).Append(',')
              .Append(F(gradientTotals[i])).Append(',')
              .Append(F(share)).Append('\n');
        }
        return sb.ToString();
    }

    static string RenderRingModeBreakdown(Data data, List<CellResult> results)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine("ring_id,mode_id,raw_contribution,share_of_ring_raw,gradient_energy,dominant_region");
        int n = data.Modes.Count;
        foreach (Ring ring in data.Rings.OrderBy(r => r.Order))
        {
            List<CellResult> group = results.Where(r => Object.ReferenceEquals(r.Cell.Ring, ring)).OrderBy(r => r.Cell.Order).ToList();
            double ringRaw = group.Sum(r => r.RawFlux);
            for (int i = 0; i < n; i++)
            {
                double raw = group.Sum(r => r.ModeContrib[i]);
                double gradient = group.Sum(r => r.GradientModeContrib[i]);
                SortedDictionary<string, double> byRegion = new SortedDictionary<string, double>(StringComparer.Ordinal);
                foreach (CellResult result in group)
                {
                    if (!byRegion.ContainsKey(result.Cell.Region))
                    {
                        byRegion[result.Cell.Region] = 0.0;
                    }
                    byRegion[result.Cell.Region] += result.ModeContrib[i];
                }
                string dominantRegion = "";
                double dominantAbs = -1.0;
                foreach (KeyValuePair<string, double> kv in byRegion)
                {
                    double abs = Math.Abs(kv.Value);
                    if (abs > dominantAbs)
                    {
                        dominantAbs = abs;
                        dominantRegion = kv.Key;
                    }
                }
                double share = ringRaw == 0.0 ? 0.0 : raw / ringRaw;
                sb.Append(ring.Id).Append(',')
                  .Append(data.Modes[i].Id).Append(',')
                  .Append(F(raw)).Append(',')
                  .Append(F(share)).Append(',')
                  .Append(F(gradient)).Append(',')
                  .Append(dominantRegion).Append('\n');
            }
        }
        return sb.ToString();
    }

    static CellResult IntegrateCell(Data data, Cell cell, double thetaMin, double thetaMax, bool includeModeAudits)
    {
        int nModes = data.Modes.Count;
        CellResult result = new CellResult(cell, nModes);
        if (!(thetaMax > thetaMin))
        {
            return result;
        }
        double muA = Math.Cos(thetaMax * Math.PI / 180.0);
        double muB = Math.Cos(thetaMin * Math.PI / 180.0);
        double muMid = 0.5 * (muA + muB);
        double muHalf = 0.5 * (muB - muA);
        double[] basis = new double[nModes];
        double[] dMuBasis = new double[nModes];
        double[] dPhiBasis = new double[nModes];
        double[] pCache = new double[nModes];

        foreach (PhiSegment seg in cell.Segments)
        {
            double phiMid = 0.5 * (seg.A + seg.B);
            double phiHalf = 0.5 * (seg.B - seg.A);
            for (int i = 0; i < data.Nodes.Length; i++)
            {
                double mu = muMid + muHalf * data.Nodes[i];
                double wMu = muHalf * data.Weights[i];
                for (int j = 0; j < data.Nodes.Length; j++)
                {
                    double phi = phiMid + phiHalf * data.Nodes[j];
                    double weight = wMu * phiHalf * data.Weights[j];
                    double field = 0.0;
                    double fieldMu = 0.0;
                    double fieldPhi = 0.0;
                    double evalPhi = phi + data.Settings.RotationRadians;
                    for (int k = 0; k < nModes; k++)
                    {
                        Mode mode = data.Modes[k];
                        double p = AssociatedLegendre(mode.Ell, mode.M, mu);
                        pCache[k] = p;
                        double cos = Math.Cos(mode.M * evalPhi);
                        double sin = Math.Sin(mode.M * evalPhi);
                        double trig = mode.Kind == 'C' ? cos : sin;
                        double dTrig = mode.Kind == 'C' ? -mode.M * sin : mode.M * cos;
                        double dp = AssociatedLegendreDerivative(mode.Ell, mode.M, mu, p);
                        basis[k] = p * trig;
                        dMuBasis[k] = dp * trig;
                        dPhiBasis[k] = p * dTrig;
                        field += mode.Coefficient * basis[k];
                        fieldMu += mode.Coefficient * dMuBasis[k];
                        fieldPhi += mode.Coefficient * dPhiBasis[k];
                    }
                    result.Area += weight;
                    result.RawFlux += cell.Exposure * field * weight;
                    result.ClippedFlux += cell.Exposure * Math.Max(field, data.Settings.ClipFloor) * weight;
                    if (field < data.Settings.ClipFloor)
                    {
                        result.ClippedNodes++;
                    }
                    for (int a = 0; a < nModes; a++)
                    {
                        result.ModeContrib[a] += cell.Exposure * data.Modes[a].Coefficient * basis[a] * weight;
                    }
                    double oneMinus = Math.Max(0.0, 1.0 - mu * mu);
                    double thetaEnergy = oneMinus * fieldMu * fieldMu;
                    double phiEnergy = oneMinus == 0.0 ? 0.0 : fieldPhi * fieldPhi / oneMinus;
                    result.ThetaEnergy += cell.Exposure * thetaEnergy * weight;
                    result.PhiEnergy += cell.Exposure * phiEnergy * weight;
                    for (int a = 0; a < nModes; a++)
                    {
                        double coeff = data.Modes[a].Coefficient;
                        double modeMu = coeff * dMuBasis[a];
                        double modePhi = coeff * dPhiBasis[a];
                        double self = oneMinus * modeMu * modeMu + (oneMinus == 0.0 ? 0.0 : modePhi * modePhi / oneMinus);
                        result.GradientModeContrib[a] += cell.Exposure * self * weight;
                    }
                    if (includeModeAudits)
                    {
                        for (int a = 0; a < nModes; a++)
                        {
                            for (int b = 0; b < nModes; b++)
                            {
                                double v = basis[a] * basis[b] * weight;
                                result.Coupling[a, b] += v;
                                result.WeightedCoupling[a, b] += cell.Exposure * v;
                            }
                        }
                    }
                }
            }
        }
        double denom = cell.Exposure * result.Area;
        if (denom != 0.0)
        {
            result.MeanRaw = result.RawFlux / denom;
            result.MeanClipped = result.ClippedFlux / denom;
        }
        return result;
    }

    static string DominantMode(Data data, double[] contrib)
    {
        int best = 0;
        double bestAbs = Math.Abs(contrib[0]);
        for (int i = 1; i < contrib.Length; i++)
        {
            double cand = Math.Abs(contrib[i]);
            if (cand > bestAbs)
            {
                bestAbs = cand;
                best = i;
            }
        }
        return data.Modes[best].Id;
    }

    static List<string[]> ReadCsv(string path, string[] expectedHeader)
    {
        if (!File.Exists(path))
        {
            throw new Exception("missing file");
        }
        string[] lines = File.ReadAllLines(path);
        if (lines.Length == 0)
        {
            throw new Exception("empty csv");
        }
        string headerLine = TrimCr(lines[0]);
        string[] header = headerLine.Split(',');
        if (header.Length != expectedHeader.Length)
        {
            throw new Exception("bad header");
        }
        for (int i = 0; i < header.Length; i++)
        {
            if (header[i] != expectedHeader[i])
            {
                throw new Exception("bad header");
            }
        }
        List<string[]> rows = new List<string[]>();
        for (int lineNo = 1; lineNo < lines.Length; lineNo++)
        {
            string line = TrimCr(lines[lineNo]);
            if (line.Length == 0)
            {
                throw new Exception("blank row");
            }
            string[] parts = line.Split(',');
            if (parts.Length != expectedHeader.Length)
            {
                throw new Exception("bad row");
            }
            rows.Add(parts);
        }
        return rows;
    }

    static string TrimCr(string text)
    {
        return text.EndsWith("\r", StringComparison.Ordinal) ? text.Substring(0, text.Length - 1) : text;
    }

    static string Token(string text)
    {
        if (String.IsNullOrEmpty(text) || text.IndexOf(',') >= 0 || text.IndexOf('\n') >= 0 || text.IndexOf('\r') >= 0 || text.IndexOf('"') >= 0)
        {
            throw new Exception("bad token");
        }
        return text;
    }

    static int ParseInt(string text)
    {
        int value;
        if (!Int32.TryParse(text, NumberStyles.Integer, Inv, out value))
        {
            throw new Exception("bad integer");
        }
        return value;
    }

    static double ParseDouble(string text)
    {
        double value;
        if (!Double.TryParse(text, NumberStyles.Float, Inv, out value) || Double.IsNaN(value) || Double.IsInfinity(value))
        {
            throw new Exception("bad number");
        }
        return value;
    }

    static List<PhiSegment> NormalizePhi(double start, double end)
    {
        double width = end - start;
        if (width == 360.0)
        {
            return new List<PhiSegment> { new PhiSegment(0.0, 2.0 * Math.PI) };
        }
        double s = start % 360.0;
        if (s < 0.0)
        {
            s += 360.0;
        }
        double e = s + width;
        List<PhiSegment> segments = new List<PhiSegment>();
        if (e <= 360.0)
        {
            segments.Add(new PhiSegment(s * Math.PI / 180.0, e * Math.PI / 180.0));
        }
        else
        {
            segments.Add(new PhiSegment(s * Math.PI / 180.0, 2.0 * Math.PI));
            segments.Add(new PhiSegment(0.0, (e - 360.0) * Math.PI / 180.0));
        }
        return segments;
    }

    static double AssociatedLegendre(int ell, int m, double x)
    {
        double pmm = 1.0;
        if (m > 0)
        {
            double somx2 = Math.Sqrt(Math.Max(0.0, (1.0 - x) * (1.0 + x)));
            double fact = 1.0;
            for (int i = 1; i <= m; i++)
            {
                pmm *= -fact * somx2;
                fact += 2.0;
            }
        }
        if (ell == m)
        {
            return pmm;
        }
        double pmmp1 = x * (2.0 * m + 1.0) * pmm;
        if (ell == m + 1)
        {
            return pmmp1;
        }
        double pll = 0.0;
        double pLm2 = pmm;
        double pLm1 = pmmp1;
        for (int l = m + 2; l <= ell; l++)
        {
            pll = ((2.0 * l - 1.0) * x * pLm1 - (l + m - 1.0) * pLm2) / (l - m);
            pLm2 = pLm1;
            pLm1 = pll;
        }
        return pll;
    }

    static double AssociatedLegendreDerivative(int ell, int m, double x, double pell)
    {
        double previous = ell == m ? 0.0 : AssociatedLegendre(ell - 1, m, x);
        return (ell * x * pell - (ell + m) * previous) / (x * x - 1.0);
    }

    static void GaussLegendre(int n, out double[] x, out double[] w)
    {
        x = new double[n];
        w = new double[n];
        int m = (n + 1) / 2;
        for (int i = 0; i < m; i++)
        {
            double z = Math.Cos(Math.PI * (i + 0.75) / (n + 0.5));
            double z1;
            double pp = 0.0;
            do
            {
                double p1 = 1.0;
                double p2 = 0.0;
                for (int j = 1; j <= n; j++)
                {
                    double p3 = p2;
                    p2 = p1;
                    p1 = ((2.0 * j - 1.0) * z * p2 - (j - 1.0) * p3) / j;
                }
                pp = n * (z * p1 - p2) / (z * z - 1.0);
                z1 = z;
                z = z1 - p1 / pp;
            }
            while (Math.Abs(z - z1) > 1e-15);
            x[i] = -z;
            x[n - 1 - i] = z;
            double weight = 2.0 / ((1.0 - z * z) * pp * pp);
            w[i] = weight;
            w[n - 1 - i] = weight;
        }
    }

    static string F(double value)
    {
        double rounded = Math.Round(value, 6, MidpointRounding.AwayFromZero);
        if (Math.Abs(rounded) < 0.0000005)
        {
            rounded = 0.0;
        }
        return rounded.ToString("0.000000", Inv);
    }

    static string JsonEscape(string text)
    {
        return text.Replace("\\", "\\\\").Replace("\"", "\\\"");
    }
}
