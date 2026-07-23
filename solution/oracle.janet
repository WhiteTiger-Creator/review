(def pi 3.14159265358979323846264338327950288)

(defn sq [x] (* x x))

(defn cube [x] (* x x x))

(defn clamp [x lo hi] (max lo (min hi x)))

(defn csv-rows [file required numeric]
  (def lines @[])
  (each raw (string/split "\n" (slurp file))
    (def line (string/trim raw))
    (unless (= line "") (array/push lines line)))
  (when (< (length lines) 2) (error (string "empty csv: " file)))
  (def headers (string/split "," (in lines 0)))
  (def indexes @{})
  (for i 0 (length headers)
    (put indexes (keyword (string/trim (in headers i))) i))
  (each field required
    (unless (has-key? indexes field)
      (error (string "missing header " field " in " file))))
  (def out @[])
  (for line-index 1 (length lines)
    (def cells (string/split "," (in lines line-index)))
    (unless (= (length cells) (length headers))
      (error (string "wrong cell count in " file)))
    (def row @{})
    (each field required
      (def raw (string/trim (in cells (in indexes field))))
      (if (in numeric field)
        (let [value (scan-number raw)]
          (when (nil? value) (error (string "nonnumeric " field " in " file)))
          (put row field value))
        (do
          (when (= raw "") (error (string "empty " field " in " file)))
          (put row field raw))))
    (array/push out row))
  out)

(def fracture-fields
  @[:id :shell_km :depth_km :viscosity :base_mm :coupling :phase_offset
    :salinity_ppt :gas_ppm])
(def fracture-numeric
  @{:shell_km true :depth_km true :viscosity true :base_mm true :coupling true
    :phase_offset true :salinity_ppt true :gas_ppm true})
(def control-fields
  @[:phases :eccentricity :ocean_pressure :temperature :cubic :memory :ridge
    :tv :tv_eps :edge_threshold :source_total :design_noise :signal_rho
    :portfolio_size :portfolio_dose :phase_gap])
(def control-numeric
  @{:phases true :eccentricity true :ocean_pressure true :temperature true
    :cubic true :memory true :ridge true :tv true :tv_eps true
    :edge_threshold true :source_total true :design_noise true :signal_rho true
    :portfolio_size true :portfolio_dose true :phase_gap true})
(def observation-fields
  @[:phase :m18 :m44 :brightness :sigma_m18 :sigma_m44 :sigma_brightness])
(def observation-numeric
  @{:phase true :m18 true :m44 true :brightness true :sigma_m18 true
    :sigma_m44 true :sigma_brightness true})
(def candidate-fields @[:candidate :phase :altitude_km :speed_kms :dose_limit])
(def candidate-numeric
  @{:phase true :altitude_km true :speed_kms true :dose_limit true})

(defn zeros [n] (array/new-filled n 0.0))

(defn matrix [rows cols]
  (def out @[])
  (repeat rows (array/push out (zeros cols)))
  out)

(defn add-cell [a row col value]
  (put (in a row) col (+ (in (in a row) col) value)))

(defn solve-linear [a b]
  (def n (length b))
  (def aug (matrix n (+ n 1)))
  (for i 0 n
    (for j 0 n (put (in aug i) j (in (in a i) j)))
    (put (in aug i) n (in b i)))
  (for col 0 n
    (var pivot col)
    (for row (+ col 1) n
      (when (> (math/abs (in (in aug row) col))
               (math/abs (in (in aug pivot) col)))
        (set pivot row)))
    (when (< (math/abs (in (in aug pivot) col)) 1e-14)
      (error "singular matrix"))
    (when (not= pivot col)
      (def tmp (in aug col))
      (put aug col (in aug pivot))
      (put aug pivot tmp))
    (def scale (in (in aug col) col))
    (for j col (+ n 1)
      (put (in aug col) j (/ (in (in aug col) j) scale)))
    (for row 0 n
      (when (not= row col)
        (def factor (in (in aug row) col))
        (for j col (+ n 1)
          (put (in aug row) j
               (- (in (in aug row) j) (* factor (in (in aug col) j))))))))
  (def answer (zeros n))
  (for i 0 n (put answer i (in (in aug i) n)))
  answer)

(defn inverse [a]
  (def n (length a))
  (def out (matrix n n))
  (for col 0 n
    (def unit (zeros n))
    (put unit col 1.0)
    (def answer (solve-linear a unit))
    (for row 0 n (put (in out row) col (in answer row))))
  out)

(defn drive [fracture control theta]
  (+ (in fracture :base_mm)
     (/ (* 900.0 (in control :eccentricity)
           (math/cos (+ theta (in fracture :phase_offset))))
        (in fracture :shell_km))
     (* 0.025 (- (in control :ocean_pressure) (in fracture :depth_km)))
     (* 0.00005 (in fracture :gas_ppm))
     (* 0.003 (+ (- (in control :temperature) 273.15)
                 (* 0.055 (in fracture :salinity_ppt))))))

(defn state-index [phase fracture count]
  (+ (* phase count) fracture))

(defn solve-periodic [fractures control]
  (def count (length fractures))
  (def phases (in control :phases))
  (def size (* phases count))
  (def drives (matrix phases count))
  (def edges (matrix phases count))
  (for phase 0 phases
    (def theta (/ (* 2.0 pi phase) phases))
    (for i 0 count
      (put (in drives phase) i (drive (in fractures i) control theta)))
    (for i 0 count
      (def following (mod (+ i 1) count))
      (when (and (> (in (in drives phase) i) (in control :edge_threshold))
                 (> (in (in drives phase) following)
                    (in control :edge_threshold)))
        (put (in edges phase) i (in (in fractures i) :coupling)))))
  (def opening (zeros size))
  (for phase 0 phases
    (for i 0 count
      (put opening (state-index phase i count)
           (max 0.0 (in (in drives phase) i)))))
  (var converged false)
  (repeat 30
    (def residual (zeros size))
    (def jacobian (matrix size size))
    (for phase 0 phases
      (def previous-phase (mod (+ phase phases -1) phases))
      (def next-phase (mod (+ phase 1) phases))
      (for i 0 count
        (def previous (mod (+ i count -1) count))
        (def following (mod (+ i 1) count))
        (def row (state-index phase i count))
        (def left (in (in edges phase) previous))
        (def right (in (in edges phase) i))
        (def x (in opening row))
        (def x-left (in opening (state-index phase previous count)))
        (def x-right (in opening (state-index phase following count)))
        (def x-before (in opening (state-index previous-phase i count)))
        (def x-after (in opening (state-index next-phase i count)))
        (def viscosity (in (in fractures i) :viscosity))
        (put residual row
             (- (+ x
                   (* (in control :cubic) viscosity (cube x))
                   (* (in control :memory) (- (* 2.0 x) x-before x-after))
                   (* left (- x x-left))
                   (* right (- x x-right)))
                (max 0.0 (in (in drives phase) i))))
        (put (in jacobian row) row
             (+ 1.0 (* 3.0 (in control :cubic) viscosity (sq x))
                (* 2.0 (in control :memory)) left right))
        (add-cell jacobian row (state-index previous-phase i count)
                  (- (in control :memory)))
        (add-cell jacobian row (state-index next-phase i count)
                  (- (in control :memory)))
        (add-cell jacobian row (state-index phase previous count) (- left))
        (add-cell jacobian row (state-index phase following count) (- right))))
    (var largest-residual 0.0)
    (each value residual
      (set largest-residual (max largest-residual (math/abs value))))
    (when (< largest-residual 1e-13)
      (set converged true)
      (break))
    (def delta (solve-linear jacobian (map |(- $) residual)))
    (for i 0 size (put opening i (+ (in opening i) (in delta i)))))
  (unless converged (error "periodic state solve did not converge"))
  (def states @[])
  (for phase 0 phases
    (def phase-states @[])
    (for i 0 count
      (def fracture (in fractures i))
      (def x (in opening (state-index phase i count)))
      (def viscosity (in fracture :viscosity))
      (def salinity (in fracture :salinity_ppt))
      (def gas (in fracture :gas_ppm))
      (def water
        (/ (* (cube x)
              (math/sqrt (max 0.0 (- (in control :ocean_pressure)
                                    (in fracture :depth_km)))))
           (* viscosity (+ 1.0 (/ salinity 100.0)))))
      (def vapor
        (clamp (+ (/ (+ (- (in control :temperature) 273.15)
                           (* 0.055 salinity))
                        18.0)
                  (/ gas 8000.0))
               0.0 0.95))
      (def m18 (* water vapor))
      (def m44 (* m18 (/ gas 4000.0)))
      (def brightness
        (/ (* water (- 1.0 vapor) (+ 1.0 (/ salinity 50.0))
              (+ 120.0 (* 280.0 vapor) (* 0.01 gas)))
           (math/sqrt 226000.0)))
      (array/push phase-states
        {:phase phase :fracture (in fracture :id) :opening_mm x
         :water_flux water :m18 m18 :m44 m44 :brightness brightness}))
    (array/push states phase-states))
  [states drives edges])

(defn state-at [states phase fracture]
  (in (in states phase) fracture))

(defn objective-gradient [weights normal projected control]
  (def count (length weights))
  (def gradient (zeros count))
  (for i 0 count
    (var value (* -2.0 (in projected i)))
    (for j 0 count
      (set value (+ value (* 2.0 (in (in normal i) j) (in weights j)))))
    (put gradient i value))
  (for i 0 count
    (def following (mod (+ i 1) count))
    (def difference (- (in weights i) (in weights following)))
    (def denominator (math/sqrt (+ (sq difference) (sq (in control :tv_eps)))))
    (def value (/ (* (in control :tv) difference) denominator))
    (put gradient i (+ (in gradient i) value))
    (put gradient following (- (in gradient following) value)))
  gradient)

(defn objective-hessian [weights normal control]
  (def count (length weights))
  (def hessian (matrix count count))
  (for i 0 count
    (for j 0 count
      (put (in hessian i) j (* 2.0 (in (in normal i) j)))))
  (for i 0 count
    (def following (mod (+ i 1) count))
    (def difference (- (in weights i) (in weights following)))
    (def denominator
      (math/pow (+ (sq difference) (sq (in control :tv_eps))) 1.5))
    (def curvature (/ (* (in control :tv) (sq (in control :tv_eps)))
                      denominator))
    (add-cell hessian i i curvature)
    (add-cell hessian following following curvature)
    (add-cell hessian i following (- curvature))
    (add-cell hessian following i (- curvature)))
  hessian)

(defn objective-value [weights normal projected control]
  (def count (length weights))
  (var value 0.0)
  (for i 0 count
    (set value (- value (* 2.0 (in projected i) (in weights i))))
    (for j 0 count
      (set value (+ value (* (in weights i) (in (in normal i) j)
                             (in weights j))))))
  (for i 0 count
    (def following (mod (+ i 1) count))
    (set value
         (+ value
            (* (in control :tv)
               (math/sqrt (+ (sq (- (in weights i) (in weights following)))
                             (sq (in control :tv_eps))))))))
  value)

(defn fit-sources [states observations fractures control]
  (def count (length fractures))
  (def normal (matrix count count))
  (def projected (zeros count))
  (for i 0 count (put (in normal i) i (in control :ridge)))
  (each observation observations
    (def phase (in observation :phase))
    (def signals [:m18 :m44 :brightness])
    (def sigmas [:sigma_m18 :sigma_m44 :sigma_brightness])
    (def covariance (matrix 3 3))
    (for a 0 3
      (for b 0 3
        (put (in covariance a) b
             (* (in observation (in sigmas a))
                (in observation (in sigmas b))
                (if (= a b) 1.0 (in control :signal_rho))))))
    (def precision (inverse covariance))
    (for i 0 count
      (for a 0 3
        (for b 0 3
          (put projected i
               (+ (in projected i)
                  (* (in (state-at states phase i) (in signals a))
                     (in (in precision a) b)
                     (in observation (in signals b)))))))
      (for j 0 count
        (for a 0 3
          (for b 0 3
            (add-cell normal i j
                      (* (in (state-at states phase i) (in signals a))
                         (in (in precision a) b)
                         (in (state-at states phase j) (in signals b)))))))))
  (var best nil)
  (var best-objective math/inf)
  (for mask 1 (math/pow 2 count)
    (def active @[])
    (for i 0 count
      (when (not= 0 (band mask (blshift 1 i))) (array/push active i)))
    (def active-count (length active))
    (def weights (zeros count))
    (for a 0 active-count
      (put weights (in active a) (/ (in control :source_total) active-count)))
    (var multiplier 0.0)
    (var converged false)
    (repeat 100
      (def gradient (objective-gradient weights normal projected control))
      (def residual (zeros (+ active-count 1)))
      (var largest 0.0)
      (for a 0 active-count
        (put residual a (+ (in gradient (in active a)) multiplier))
        (set largest (max largest (math/abs (in residual a)))))
      (var total (- (in control :source_total)))
      (each weight weights (set total (+ total weight)))
      (put residual active-count total)
      (set largest (max largest (math/abs total)))
      (when (< largest 1e-11)
        (set converged true)
        (break))
      (def hessian (objective-hessian weights normal control))
      (def kkt (matrix (+ active-count 1) (+ active-count 1)))
      (for a 0 active-count
        (put (in kkt a) active-count 1.0)
        (put (in kkt active-count) a 1.0)
        (for b 0 active-count
          (put (in kkt a) b
               (in (in hessian (in active a)) (in active b)))))
      (def delta (solve-linear kkt (map |(- $) residual)))
      (var step 1.0)
      (for a 0 active-count
        (when (< (in delta a) 0.0)
          (set step
               (min step (/ (* -0.99 (in weights (in active a)))
                            (in delta a))))))
      (for a 0 active-count
        (def index (in active a))
        (put weights index (+ (in weights index) (* step (in delta a)))))
      (set multiplier (+ multiplier (* step (in delta active-count)))))
    (when converged
      (var valid true)
      (each index active
        (when (< (in weights index) -1e-10) (set valid false)))
      (when valid
        (def value (objective-value weights normal projected control))
        (when (< value best-objective)
          (set best-objective value)
          (set best weights)))))
  (when (nil? best) (error "source reconstruction failed"))
  best)

(defn logdet-spd [a]
  (def count (length a))
  (def l (matrix count count))
  (var answer 0.0)
  (for i 0 count
    (for j 0 (+ i 1)
      (var value (in (in a i) j))
      (for k 0 j
        (set value (- value (* (in (in l i) k) (in (in l j) k)))))
      (if (= i j)
        (do
          (when (<= value 0.0)
            (error "information matrix is not positive definite"))
          (put (in l i) j (math/sqrt value))
          (set answer (+ answer (* 2.0 (math/log (in (in l i) j))))))
        (put (in l i) j (/ value (in (in l j) j))))))
  answer)

(defn design-portfolio [states candidates fractures control]
  (def count (length fractures))
  (def rows @[])
  (def contributions @[])
  (each candidate candidates
    (def phase (in candidate :phase))
    (def attenuation
      (/ (math/exp (/ (- (in candidate :altitude_km)) 180.0))
         (in candidate :speed_kms)))
    (def contribution (matrix count count))
    (for i 0 count
      (for j 0 count
        (var dot 0.0)
        (each signal [:m18 :m44 :brightness]
          (set dot
               (+ dot
                  (* attenuation (in (state-at states phase i) signal)
                     attenuation (in (state-at states phase j) signal)))))
        (put (in contribution i) j
             (/ dot (sq (in control :design_noise))))))
    (array/push contributions contribution)
    (def singleton (matrix count count))
    (for i 0 count
      (for j 0 count
        (put (in singleton i) j
             (+ (if (= i j) 1.0 0.0) (in (in contribution i) j)))))
    (var total-water 0.0)
    (for i 0 count
      (set total-water (+ total-water (in (state-at states phase i) :water_flux))))
    (def dose
      (/ (* total-water (math/exp (/ (- (in candidate :altitude_km)) 120.0)))
         (in candidate :speed_kms)))
    (array/push rows
      @{:candidate (in candidate :candidate) :score (logdet-spd singleton)
        :dose dose :feasible (<= dose (in candidate :dose_limit))
        :selected false}))
  (var best-mask nil)
  (var best-score (- math/inf))
  (var best-dose 0.0)
  (def candidate-count (length candidates))
  (for mask 0 (math/pow 2 candidate-count)
    (def chosen @[])
    (for i 0 candidate-count
      (when (not= 0 (band mask (blshift 1 i))) (array/push chosen i)))
    (when (= (length chosen) (in control :portfolio_size))
      (var valid true)
      (var dose 0.0)
      (each index chosen
        (unless (in (in rows index) :feasible) (set valid false))
        (set dose (+ dose (in (in rows index) :dose))))
      (when (> dose (in control :portfolio_dose)) (set valid false))
      (for a 0 (length chosen)
        (for b (+ a 1) (length chosen)
          (def pa (in (in candidates (in chosen a)) :phase))
          (def pb (in (in candidates (in chosen b)) :phase))
          (def difference (math/abs (- pa pb)))
          (def separation (min difference (- (in control :phases) difference)))
          (when (< separation (in control :phase_gap)) (set valid false))))
      (when valid
        (def information (matrix count count))
        (for i 0 count (put (in information i) i 1.0))
        (each index chosen
          (for i 0 count
            (for j 0 count
              (add-cell information i j
                        (in (in (in contributions index) i) j)))))
        (def score (logdet-spd information))
        (when (> score best-score)
          (set best-score score)
          (set best-dose dose)
          (set best-mask mask)))))
  (when (nil? best-mask) (error "no feasible flyby portfolio"))
  (for i 0 candidate-count
    (when (not= 0 (band best-mask (blshift 1 i)))
      (put (in rows i) :selected true)))
  [rows best-score best-dose])

(defn sql-quote [value]
  (string "'" (string/replace-all "'" "''" value) "'"))

(defn write-database [output-dir states fractures weights flybys portfolio-score
                      portfolio-dose]
  (os/execute @["/bin/mkdir" "-p" output-dir] :x)
  (def database (string output-dir "/plume.db"))
  (def script (string output-dir "/plume.sql"))
  (when (os/stat database) (os/rm database))
  (def sql @"")
  (buffer/push-string sql
    "PRAGMA journal_mode=DELETE;\nBEGIN;\nDROP TABLE IF EXISTS state;\nDROP TABLE IF EXISTS reconstruction;\nDROP TABLE IF EXISTS flyby;\nDROP TABLE IF EXISTS portfolio;\n")
  (buffer/push-string sql
    "CREATE TABLE state(phase INTEGER NOT NULL, fracture TEXT NOT NULL, opening_mm REAL NOT NULL, water_flux REAL NOT NULL, m18 REAL NOT NULL, m44 REAL NOT NULL, brightness REAL NOT NULL, PRIMARY KEY(phase, fracture));\n")
  (buffer/push-string sql
    "CREATE TABLE reconstruction(fracture TEXT PRIMARY KEY, weight REAL NOT NULL);\n")
  (buffer/push-string sql
    "CREATE TABLE flyby(candidate TEXT PRIMARY KEY, score REAL NOT NULL, dose REAL NOT NULL, feasible INTEGER NOT NULL, selected INTEGER NOT NULL);\n")
  (buffer/push-string sql
    "CREATE TABLE portfolio(score REAL NOT NULL, total_dose REAL NOT NULL);\n")
  (each phase-states states
    (each row phase-states
      (buffer/format sql
        "INSERT INTO state VALUES(%d,%s,%.17g,%.17g,%.17g,%.17g,%.17g);\n"
        (in row :phase) (sql-quote (in row :fracture)) (in row :opening_mm)
        (in row :water_flux) (in row :m18) (in row :m44) (in row :brightness))))
  (for i 0 (length fractures)
    (buffer/format sql "INSERT INTO reconstruction VALUES(%s,%.17g);\n"
      (sql-quote (in (in fractures i) :id)) (in weights i)))
  (each row flybys
    (buffer/format sql "INSERT INTO flyby VALUES(%s,%.17g,%.17g,%d,%d);\n"
      (sql-quote (in row :candidate)) (in row :score) (in row :dose)
      (if (in row :feasible) 1 0) (if (in row :selected) 1 0)))
  (buffer/format sql "INSERT INTO portfolio VALUES(%.17g,%.17g);\n"
                 portfolio-score portfolio-dose)
  (buffer/push-string sql "COMMIT;\n")
  (spit script sql)
  (os/execute @["/usr/bin/sqlite3" database (string ".read " script)] :x)
  (os/rm script))

(defn run-simulator []
  (def args (dyn :args))
  (unless (= (length args) 3)
    (error "usage: janet main.janet INPUT_DIR OUTPUT_DIR"))
  (def input-root (in args 1))
  (def output-dir (in args 2))
  (def fractures
    (csv-rows (string input-root "/fractures.csv") fracture-fields fracture-numeric))
  (def control-rows
    (csv-rows (string input-root "/control.csv") control-fields control-numeric))
  (unless (= (length control-rows) 1) (error "control.csv must have one row"))
  (def control (in control-rows 0))
  (unless (and (= (in control :phases) (math/floor (in control :phases)))
               (> (in control :phases) 2)
               (>= (in control :memory) 0.0)
               (> (in control :ridge) 0.0)
               (>= (in control :tv) 0.0)
               (> (in control :tv_eps) 0.0)
               (> (in control :source_total) 0.0)
               (> (in control :design_noise) 0.0)
               (> (in control :signal_rho) -0.5)
               (< (in control :signal_rho) 1.0)
               (= (in control :portfolio_size)
                  (math/floor (in control :portfolio_size)))
               (> (in control :portfolio_size) 0)
               (> (in control :portfolio_dose) 0.0)
               (>= (in control :phase_gap) 0.0))
    (error "invalid control values"))
  (def seen @{})
  (each fracture fractures
    (def id (in fracture :id))
    (when (has-key? seen id) (error (string "duplicate fracture id " id)))
    (put seen id true)
    (unless (and (> (in fracture :shell_km) 0.0)
                 (> (in fracture :viscosity) 0.0)
                 (>= (in fracture :coupling) 0.0))
      (error (string "invalid fracture values for " id))))
  (def observations @[])
  (def observation-dir (string input-root "/observations"))
  (def observation-files @[])
  (each name (os/dir observation-dir)
    (when (string/has-suffix? ".csv" name) (array/push observation-files name)))
  (sort observation-files)
  (when (= 0 (length observation-files)) (error "no observation csv files"))
  (each name observation-files
    (each row (csv-rows (string observation-dir "/" name)
                        observation-fields observation-numeric)
      (unless (and (= (in row :phase) (math/floor (in row :phase)))
                   (>= (in row :phase) 0)
                   (< (in row :phase) (in control :phases)))
        (error "observation phase outside grid"))
      (each sigma [:sigma_m18 :sigma_m44 :sigma_brightness]
        (unless (> (in row sigma) 0.0) (error "nonpositive observation sigma")))
      (array/push observations row)))
  (def candidates
    (csv-rows (string input-root "/candidates.csv") candidate-fields candidate-numeric))
  (each candidate candidates
    (unless (and (= (in candidate :phase) (math/floor (in candidate :phase)))
                 (>= (in candidate :phase) 0)
                 (< (in candidate :phase) (in control :phases))
                 (> (in candidate :speed_kms) 0.0)
                 (> (in candidate :dose_limit) 0.0))
      (error "invalid candidate")))
  (when (> (in control :portfolio_size) (length candidates))
    (error "portfolio exceeds candidate count"))
  (def [states] (solve-periodic fractures control))
  (def weights (fit-sources states observations fractures control))
  (def [flybys portfolio-score portfolio-dose]
    (design-portfolio states candidates fractures control))
  (write-database output-dir states fractures weights flybys portfolio-score
                  portfolio-dose))

(try
  (run-simulator)
  ([err]
    (eprin err)
    (os/exit 2)))
