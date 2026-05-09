# Adaptive Kalman + AMPC Research Notes

> Last updated: 2026-04-14
> Source notes: `BaoCao.md`, `Tonghop.md`, `Tonghop2.md`

---

## 1. Ket luan dieu chinh huong lam

Ba file moi cho thay huong dung cua do an khong nen dung o "Kalman + MPC" co ban. Huong can bam la:

- **Adaptive Kalman** cho uoc luong trang thai trong moi truong nha kinh co nhieu nhieu, tre, nhieu bien va dieu kien thay doi theo thoi gian.
- **AMPC - Adaptive Model Predictive Control** cho tang dieu khien toi uu ve sau, dac biet voi tuoi nho giot, phun suong va quat.
- **ARX hien co** nen duoc xem la baseline prediction model ban dau, khong nen dong kien truc vao ARX vinh vien.
- **LightGBM/XGBoost** la ung vien prediction model ve sau neu du lieu bang thoi gian du sach va scope cho phep.

V1 van nen lam theo tung buoc de co ket qua bao ve duoc: ingestion -> preprocessing -> prediction adapter -> Adaptive Kalman-ready estimator -> logging -> evaluation -> visualization. Khac biet la cac interface, metric va tai lieu phai duoc thiet ke de khong chan AMPC.

---

## 2. Phan huu ich rut ra tu tung file

### `BaoCao.md`

- Cung cap khung bao cao hoc thuat: ly thuyet MPC/HMPC, Kalman variants, prediction model, FAO-56, cost function, constraints, simulation/evaluation.
- Co bo metric tot cho so sanh dieu khien: RMSE, luong nuoc, nang luong, thoi gian stress, actuator switching.
- Co cac rang buoc thuc dung: drip/mist duration, daily max water, soil moisture/RH bounds, emergency fallback, sensor fault fallback, khong phun suong khi RH cao hoac ban dem.
- Co goi y so sanh rule-based, PID, MPC, HMPC/AMPC. Nen giu de lam phan danh gia sau khi estimator on dinh.

### `Tonghop.md`

- Lam ro logic nen chon **Adaptive MPC** thay vi MPC LTI co dinh, vi nha kinh co diem van hanh thay doi theo nang, nhiet do, do am va bay hoi.
- Giai thich pipeline dung: Optimization block -> Prediction model -> Kalman state estimation -> Plant -> measured/unmeasured disturbances.
- Nhac cach Adaptive MPC cap nhat model/parameter bang sai lech giua du doan va sensor thuc.
- Nhac range/zone cost phu hop voi cay trong hon exact setpoint, vi cay chap nhan mien an toan.
- Co FAO-56 logic: TAW, RAW, root-zone depletion, tuoi truoc khi vuot nguong stress.

### `Tonghop2.md`

- Huu ich nhat cho thuc thi ky thuat:
  - Dataset generator can co day/night, seasonality, inertia vat ly, actuator causality va excitation.
  - ARX(2,2,1) la baseline hop ly hon ARX(3,1,1) trong ghi chu hien co.
  - State AMPC co the chon `Dr` root-zone depletion hoac `theta` soil moisture.
  - Control input ban dau co the la `u_k = pump/drip seconds`.
  - Disturbances: ET0/ETc, temperature, RH, light.
  - Equation starter: `Dr,k+1 = Dr,k + ETc,k - (eta Q / A) u_k`.
  - Conversion starter: `TAW = 1000(thetaFC - thetaWP)Zr`, `Dr = 1000(thetaFC - theta)Zr`, `theta = thetaFC - Dr/(1000Zr)`.

---

## 3. Cap nhat workflow de khong lech huong

### Phase A - Chot bai toan va bien

Task #001 phai chot:

- Bien uoc luong Adaptive Kalman dau tien: soil moisture `theta`, root-zone depletion `Dr`, hay ca hai.
- Co che adaptive toi thieu cho v1: vi du innovation/residual-driven tuning cho `Q`/`R`, hoac heuristic cap nhat covariance co gioi han.
- Input/measurement mapping tu dataset ARX: `Soil_Moisture`, `Temperature`, `Humidity`, `Light`, `Drip`, `Mist`, `Fan`.
- Ranh gioi AMPC v1: document + contract truoc, hay prototype optimizer toi thieu.
- Prediction model ban dau: ARX adapter truoc, LightGBM/XGBoost la ung vien thay the ve sau.

### Phase B - Data va prediction boundary

- Giu `../ARX/` la read-only reference.
- Dung ARX hien co lam adapter baseline.
- Tach interface prediction model de sau nay thay bang LightGBM/XGBoost khong phai viet lai estimator/controller.
- Neu sinh data, generator can giu tinh nhan qua actuator va co excitation de du lieu du giau cho identification.
- Training/evaluation split phai theo thoi gian, khong shuffle ngau nhien, de tranh data leakage.

### Phase C - Adaptive Kalman estimator

- Estimator phai xuat: prediction, filtered estimate, residual/innovation, covariance/uncertainty, adaptive parameter status.
- Neu measurement missing/noisy: duoc phep skip update, giu last valid, hoac tang uncertainty theo rule da chot.
- Neu dung adaptive `Q`/`R`, phai log rule, bound va ly do cap nhat de bao cao khong bi "hop den".

### Phase D - AMPC-ready contract

Chua can full autonomous actuation ngay, nhung code/docs nen giu contract:

- State candidate: `Dr` hoac `theta`.
- Control input: drip/pump seconds, mist seconds, fan level/duration.
- Disturbances: ET0/ETc, temperature, humidity, light, optional CO2 neu co du lieu.
- Output: soil moisture sensor va cac bien moi truong can hien thi.
- Cost terms: zone/range tracking, water/resource penalty, energy penalty, actuator switching penalty, `Delta u` smoothing.
- Safety constraints: min/max soil moisture, RH max, daily water cap, no mist at high RH/night, emergency fallback, sensor-fault fallback.

### Phase E - Evaluation

Ngoai metric Kalman hien co, can them metric de chuan bi AMPC:

- RMSE/MAE cua du doan va uoc luong.
- Residual/innovation stability.
- Variance reduction co gioi han, khong chi lam muot qua muc.
- Luong nuoc mo phong, nang luong, thoi gian cay bi stress.
- So lan actuator switching neu co controller simulation.
- Reproducibility tu cung dataset/config.

---

## 4. Ranh gioi scope de lam dung ma khong qua tay

- **Trong scope gan**: Adaptive Kalman-ready estimator, logging residual/covariance/adaptive status, AMPC state/control/disturbance/cost/safety contract, ARX baseline adapter.
- **Trong scope sau khi #001 chot**: adaptive `Q`/`R` toi thieu hoac AMPC optimizer prototype toi thieu neu can cho bao cao.
- **Chua nen lam ngay**: full closed-loop actuator scheduler, multi-zone greenhouse, online model registry, RL controller, EKF/UKF/EnKF comparison day du.

---

## 5. Anh huong truc tiep len backlog

- #001 can doi thanh task chot **Adaptive Kalman + AMPC v1 decisions**.
- #004 ARX adapter can giu boundary thay the duoc cho LightGBM/XGBoost.
- #005 da duoc dinh huong thanh **Adaptive Kalman-ready estimation cycle** thay vi "standard Kalman only".
- Can them task docs cho **AMPC state/cost/safety synthesis** de sau nay khong mat cac chi tiet FAO-56, VPD, constraints va fallback.
