param(
    [string]$InputPath = "ARX_Model_Notebook.ipynb",
    [string]$OutputPath = "ARX_Model_Notebook_VI.ipynb"
)

$ErrorActionPreference = "Stop"

function Replace-Text {
    param(
        [string]$Text,
        [hashtable]$Map
    )

    $result = $Text
    foreach ($key in $Map.Keys) {
        $result = $result.Replace($key, $Map[$key])
    }
    return $result
}

$replacements = [ordered]@{
    "# Experiment: ARX Greenhouse Identification Study" = "# Nghien cuu nhan dang ARX cho nha kinh mini"
    "Objective:" = "Muc tieu:"
    "- Evaluate the ARX greenhouse baseline with the structure and evidence density expected in a research-style report." = "- Danh gia baseline ARX cua nha kinh voi cau truc va muc do bang chung phu hop cho mot bao cao kieu nghien cuu."
    "- Emphasize full-year data coverage, parameter recovery, long-horizon prediction, residual diagnostics, and model-structure tradeoffs." = "- Nhan manh pham vi du lieu 1 nam, kha nang thu hoi tham so, du doan dai han, chuan doan phan du, va trade-off giua cac cau truc mo hinh."
    "## Study Questions" = "## Cau hoi nghien cuu"
    "- Does the baseline ARX(2,2,1) recover the true physical direction of each actuator and disturbance term?" = "- Baseline ARX(2,2,1) co thu hoi dung huong tac dong vat ly cua tung actuator va tung thanh phan nhieu hay khong?"
    "- How far does free-run performance fall relative to one-step prediction, and is that gap explained by process noise?" = "- Hieu nang free-run giam bao nhieu so voi du doan 1-step, va khoang cach do co duoc giai thich boi nhieu qua trinh hay khong?"
    "- Which diagnostic plots are needed to argue that the model is statistically defensible rather than merely visually plausible?" = "- Can nhung bieu do chuan doan nao de co the lap luan rang mo hinh dang tin ve mat thong ke, khong chi dep ve mat thi giac?"
    "## Workflow" = "## Quy trinh"
    "1. Configure the experiment and plotting style." = "1. Cau hinh thi nghiem va kieu trinh bay bieu do."
    "2. Run the full pipeline and cache all derived tables." = "2. Chay toan bo pipeline va tao cac bang trung gian."
    "3. Characterize the dataset and operating regime." = "3. Mo ta bo du lieu va che do van hanh."
    "4. Analyze parameter recovery, prediction quality, residual behavior, and model selection." = "4. Phan tich kha nang thu hoi tham so, chat luong du doan, hanh vi phan du, va viec lua chon mo hinh."
    "5. Conclude with strengths, limits, and what the baseline can and cannot support." = "5. Ket luan ve diem manh, han che, va nhung gi baseline co the ho tro hoac chua ho tro duoc."
    "## Executive Evaluation" = "## Danh gia tong quan"
    "## Experimental Setup" = "## Thiet lap thi nghiem"
    "## Dataset Characterization" = "## Dac trung bo du lieu"
    "## Parameter Identification" = "## Nhan dang tham so"
    "## Scale-Aware Parameter Importance" = "## Muc do quan trong tham so co xet thang do"
    "## Predictive Performance" = "## Hieu nang du doan"
    "## Residual Diagnostics" = "## Chan doan phan du"
    "## Model Structure Search" = "## Tim kiem cau truc mo hinh"
    "## Conclusion And Gaps" = "## Ket luan va khoang trong"
    "This section separates one-step accuracy from long-horizon behavior and compares the baseline against the free-run-optimal order found by the search." = "Phan nay tach rieng do chinh xac 1-step voi hanh vi dai han, dong thoi so sanh baseline voi cau truc toi uu theo free-run tim duoc trong qua trinh search."
    "A research-style identification section needs more than a coefficient table. It should show estimated-vs-true comparison, confidence intervals, and stability of the autoregressive part." = "Mot phan nhan dang theo phong cach nghien cuu khong chi dung lai o bang he so. No can the hien so sanh estimate-voi-true, khoang tin cay, va do on dinh cua phan tu hoi quy."
    "Raw ARX coefficients are reported in the original engineering units, so their magnitudes are not directly comparable across regressors." = "Cac he so ARX goc duoc bao cao tren don vi ky thuat ban dau, vi vay do lon cua chung khong the so sanh truc tiep giua cac regressor."
    "The next three figures answer a fairer question: which terms matter most after accounting for variable scale, operating distribution, and lagged dynamic propagation." = "Ba hinh tiep theo tra loi mot cau hoi cong bang hon: term nao quan trong nhat sau khi da tinh den thang do bien, phan bo van hanh, va tac dong dong hoc co do tre."
    "The notebook should not stop at a pretty one-step score. A defensible identification result must combine:" = "Notebook khong nen dung lai o mot diem so 1-step dep. Mot ket qua nhan dang dang tin can ket hop:"
    "- representative data coverage," = "- du lieu co pham vi dai dien,"
    "- parameter signs consistent with the generating physics," = "- dau tham so phu hop voi vat ly sinh du lieu,"
    "- residuals that behave like unexplained noise," = "- phan du co hanh vi giong nhieu chua giai thich,"
    "- and long-horizon performance interpreted relative to the deterministic ceiling." = "- va hieu nang dai han duoc dien giai tuong quan voi gioi han xac dinh."
    "This section documents the baseline configuration and the operating statistics of each split. In a paper, this is the minimum needed to interpret the downstream metrics." = "Phan nay ghi lai cau hinh baseline va thong ke van hanh cua tung split. Trong mot bai bao, day la muc toi thieu can co de dien giai cac metric o phan sau."
    "The original notebook lacked several paper-level figures: a full-year operating overview, monthly distributions, actuator-duty evolution, and setpoint occupancy. Those are added below." = "Notebook ban dau con thieu mot so hinh mang tinh bao cao nghien cuu: tong quan van hanh ca nam, phan bo theo thang, su thay doi duty cycle cua actuator, va ty le bam setpoint. Cac noi dung do duoc bo sung ben duoi."
    "The earlier notebook only partially covered diagnostics. A research-style report needs residual tables, Q-Q evidence, autocorrelation, Ljung-Box p-values, and correlation against inputs." = "Notebook truoc day moi chi bao phu mot phan chuan doan. Mot bao cao kieu nghien cuu can co bang phan du, Q-Q plot, tu tuong quan, p-value Ljung-Box, va tuong quan giua phan du voi input."
    "A paper should show the search landscape, not just the winner. This section adds both the Pareto-style scatter and na-nb heatmaps for different delays." = "Mot bao cao nen the hien ca bo mat tim kiem mo hinh, khong chi dua ra nguoi thang cuoc. Phan nay bo sung ca do thi kieu Pareto va heatmap na-nb cho cac gia tri tre khac nhau."
    "- The notebook now includes the figures that were missing for a paper-like presentation: full-year operating overview, monthly distributions, actuator-duty evolution, setpoint occupancy, parameter recovery with confidence intervals, stability plot, calibration scatter, rolling error, residual diagnostics, Ljung-Box p-values, and model-search heatmaps." = "- Notebook hien da bo sung cac hinh con thieu cho mot bai trinh bay kieu paper: tong quan van hanh ca nam, phan bo theo thang, bien thien duty cycle actuator, muc bam setpoint, thu hoi tham so kem khoang tin cay, bieu do on dinh, calibration scatter, rolling error, residual diagnostics, p-value Ljung-Box, va heatmap search mo hinh."
    "- The baseline ARX(2,2,1) is strong as an interpretable identification model because it recovers all parameter signs and passes residual whiteness checks." = "- Baseline ARX(2,2,1) manh voi tu cach mot mo hinh nhan dang co the giai thich duoc, vi no thu hoi dung dau tat ca tham so va vuot qua kiem tra residual whiteness."
    "- The large gap between one-step and free-run metrics remains, but it is now shown alongside the theoretical deterministic ceiling, which makes the result interpretable rather than suspicious." = "- Khoang cach lon giua 1-step va free-run van ton tai, nhung hien da duoc dat canh gioi han xac dinh ly thuyet, nen ket qua tro nen de dien giai hon thay vi dang nghi."
    "- The order search shows that a different structure can improve free-run validation metrics slightly, but that does not automatically make it the best model for structure recovery or controller design." = "- Qua trinh search bac mo hinh cho thay mot cau truc khac co the cai thien metric free-run tren validation, nhung dieu do khong tu dong bien no thanh mo hinh tot nhat cho viec thu hoi cau truc hoac thiet ke dieu khien."
    "Performance interpretation" = "Dien giai hieu nang"
    "Trace interpretation" = "Dien giai do thi bam tin hieu"
    "Calibration interpretation" = "Dien giai calibration"
    "Monthly generalization interpretation" = "Dien giai kha nang tong quat hoa theo thang"
    "Seasonality interpretation" = "Dien giai tinh mua vu"
    "Actuator and setpoint interpretation" = "Dien giai actuator va setpoint"
    "Parameter interpretation" = "Dien giai tham so"
    "Standardized-coefficient interpretation" = "Dien giai he so chuan hoa"
    "Contribution interpretation" = "Dien giai muc dong gop"
    "Impulse-response interpretation" = "Dien giai dap ung xung"
    "Residual summary interpretation" = "Dien giai tong quan phan du"
    "Residual-panel interpretation" = "Dien giai cum bieu do phan du"
    "Ljung-Box interpretation" = "Dien giai Ljung-Box"
    "Search-table interpretation" = "Dien giai bang search"
    "Search-frontier interpretation" = "Dien giai bien Pareto"
    "Heatmap interpretation" = "Dien giai heatmap"
    "Validation one-step prediction" = "Validation du doan 1 buoc"
    "Test one-step prediction" = "Test du doan 1 buoc"
    "Validation long-horizon behavior" = "Validation hanh vi dai han"
    "Test long-horizon behavior" = "Test hanh vi dai han"
    "Validation calibration scatter" = "Validation calibration scatter"
    "Test calibration scatter" = "Test calibration scatter"
    "Validation free-run rolling RMSE (1 day window)" = "Validation RMSE cua so truot free-run (cua so 1 ngay)"
    "Test free-run rolling RMSE (1 day window)" = "Test RMSE cua so truot free-run (cua so 1 ngay)"
    "Validation monthly free-run metrics" = "Validation metric free-run theo thang"
    "Test monthly free-run metrics" = "Test metric free-run theo thang"
    "Monthly distribution of Soil_Moisture" = "Phan bo theo thang cua Soil_Moisture"
    "Monthly distribution of Temperature" = "Phan bo theo thang cua Temperature"
    "Monthly distribution of Humidity" = "Phan bo theo thang cua Humidity"
    "Monthly distribution of Light" = "Phan bo theo thang cua Light"
    "Monthly actuator duty cycle" = "Duty cycle actuator theo thang"
    "Monthly switching count" = "So lan chuyen trang thai theo thang"
    "Monthly setpoint occupancy" = "Ty le bam setpoint theo thang"
    "Parameter recovery with 95% CI" = "Thu hoi tham so voi khoang tin cay 95%"
    "AR roots in the complex plane" = "Cac nghiem AR tren mat phang phuc"
    "Standardized coefficient magnitude on the training split" = "Do lon he so chuan hoa tren tap train"
    "Average absolute regressor contribution on the training split" = "Dong gop tuyet doi trung binh cua tung regressor tren tap train"
    "Impulse response to one-standard-deviation input pulses" = "Dap ung xung voi xung input bang 1 do lech chuan"
    "Cumulative effect of the same pulses" = "Tac dong tich luy cua cung nhung xung do"
    "Full-year Soil_Moisture overview" = "Tong quan Soil_Moisture ca nam"
    "Full-year Temperature overview" = "Tong quan Temperature ca nam"
    "Full-year Humidity overview" = "Tong quan Humidity ca nam"
    "Full-year Light overview" = "Tong quan Light ca nam"
    "Actuator activity overview" = "Tong quan hoat dong actuator"
    "Validation residuals over time" = "Phan du Validation theo thoi gian"
    "Residual histogram" = "Histogram phan du"
    "Q-Q plot" = "Do thi Q-Q"
    "Residual autocorrelation" = "Tu tuong quan phan du"
    "Residual vs fitted" = "Phan du theo gia tri fitted"
    "Residual-input correlation" = "Tuong quan giua phan du va input"
    "Validation Ljung-Box p-values" = "P-value Ljung-Box tren Validation"
    "Test Ljung-Box p-values" = "P-value Ljung-Box tren Test"
    "Free-run Pareto frontier" = "Bien Pareto cho free-run"
    "Top-10 structures by free-run RMSE" = "Top 10 cau truc theo RMSE free-run"
    "RMSE_sim heatmap for nk=1" = "Heatmap RMSE_sim cho nk=1"
    "RMSE_sim heatmap for nk=2" = "Heatmap RMSE_sim cho nk=2"
    "Sample index" = "Chi so mau"
    "Split" = "Tap"
    "Soil Moisture (%)" = "Do am dat (%)"
    "1-step" = "1 buoc"
    "12-step" = "12 buoc"
    "Free-run" = "Free-run"
    "Actual " = "Thuc te "
    "Predicted " = "Du doan "
    "Actual" = "Thuc te"
    "Predicted" = "Du doan"
    "RMSE" = "RMSE"
    "FIT (%)" = "FIT (%)"
    "ON percentage" = "Ty le ON"
    "Switch count" = "So lan chuyen"
    "Percentage of time" = "Phan tram thoi gian"
    "Below low SP" = "Duoi low SP"
    "Inside band" = "Trong dai"
    "Above high SP" = "Tren high SP"
    "Coefficient value" = "Gia tri he so"
    "Real part" = "Phan thuc"
    "Imaginary part" = "Phan ao"
    "Standardized beta = theta_i * std(x_i) / std(y)" = "Beta chuan hoa = theta_i * std(x_i) / std(y)"
    "Mean |x_i * theta_i|" = "Gia tri trung binh |x_i * theta_i|"
    "Step ahead" = "Buoc du bao"
    "Instantaneous output response" = "Dap ung dau ra tuc thoi"
    "Cumulative response" = "Dap ung tich luy"
    "Evidence" = "Bang chung"
    "Finding" = "Phat hien"
    "Source" = "Nguon"
    "Days" = "So ngay"
    "Sampling seconds" = "So giay lay mau"
    "Train ratio" = "Ti le train"
    "Validation ratio" = "Ti le validation"
    "Test ratio" = "Ti le test"
    "Setting" = "Cau hinh"
    "Value" = "Gia tri"
    "Block" = "Khoi"
    "Best free-run model" = "Mo hinh free-run tot nhat"
    "Baseline ARX" = "Baseline ARX"
    "Best free-run ARX" = "ARX free-run tot nhat"
}

$inputFullPath = Join-Path (Get-Location) $InputPath
$outputFullPath = Join-Path (Get-Location) $OutputPath

$raw = Get-Content $inputFullPath -Raw -Encoding UTF8
$notebook = $raw | ConvertFrom-Json

foreach ($cell in $notebook.cells) {
    $translatedSource = @()
    foreach ($line in $cell.source) {
        $translatedSource += (Replace-Text -Text $line -Map $replacements)
    }
    $cell.source = $translatedSource

    if ($cell.cell_type -eq "code") {
        $cell.execution_count = $null
        $cell.outputs = @()
    }
}

$json = $notebook | ConvertTo-Json -Depth 100
Set-Content -Path $outputFullPath -Value $json -Encoding UTF8

Write-Output "Da tao notebook tieng Viet tai: $outputFullPath"
