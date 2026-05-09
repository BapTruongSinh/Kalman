# Vì sao nên đọc `backend/estimation/models.py` trước

File gốc: `Server/backend/estimation/models.py`

File này định nghĩa schema database bằng Django ORM. Nói đơn giản: mỗi class trong file này tương ứng với một bảng trong MySQL, mỗi field tương ứng với một cột, còn `Meta` định nghĩa tên bảng, index, unique constraint và check constraint.

Nếu muốn hiểu luồng Kalman của project, nên đọc file này trước vì nó trả lời 3 câu hỏi nền tảng:

1. Dữ liệu raw lưu ở đâu.
2. Dữ liệu dự đoán ARX và dữ liệu sau Kalman lưu ở đâu.
3. Metric train / validation / test được lưu ở đâu.

## Các thứ được import

| Dòng | Code | Dùng gì | Nó đến từ đâu | Ý nghĩa |
|---:|---|---|---|---|
| 8 | `from django.conf import settings` | `settings` | Thư viện Django | Lấy cấu hình Django hiện tại, ở đây dùng `settings.AUTH_USER_MODEL` để liên kết user. |
| 9 | `from django.db import models` | `models` | Thư viện Django ORM | Cung cấp `Model`, `CharField`, `FloatField`, `ForeignKey`, `Index`, `Constraint`... để khai báo bảng DB bằng Python. |

## Các class chính trong file

| Class | Bảng DB | Vai trò |
|---|---|---|
| `ExperimentRun` | `experiment_runs` | Bảng gốc, mỗi dòng là một lần chạy demo / live. |
| `ExperimentConfig` | `experiment_configs` | Lưu cấu hình cố định của một run. |
| `ARXArtifact` | `arx_artifacts` | Lưu hệ số và metric của model ARX đã train. |
| `PipelineCycle` | `pipeline_cycles` | Bảng dữ liệu lõi, mỗi dòng là một bước xử lý. Có raw, ARX predicted, Kalman filtered. |
| `EvaluationSummary` | `evaluation_summaries` | Lưu metric tổng hợp theo train / validation / test. |

## Giải thích từng dòng

### Dòng 1-10: mô tả file và import

| Dòng | Có gì trong dòng | Dùng gì | Giải thích |
|---:|---|---|---|
| 1 | Mở docstring `"""` | Cú pháp Python mặc định | Bắt đầu phần ghi chú nhiều dòng của module. Không ảnh hưởng logic chạy. |
| 2 | Mô tả đây là model Django ORM | Docstring Python | Nói file này định nghĩa ORM cho pipeline Adaptive Kalman. |
| 3 | Dòng trống trong docstring | Python | Chỉ để dễ đọc. |
| 4 | Nhắc schema được thiết kế ở task #002 | Docstring | Gợi ý tài liệu liên quan là `docs/technical/DATABASE.md`. |
| 5 | Nhắc charset `utf8mb4` | Django database config | Ý nói DB hỗ trợ Unicode đầy đủ, gồm tiếng Việt và ký tự đặc biệt. |
| 6 | Đóng docstring | Cú pháp Python | Kết thúc ghi chú module. |
| 7 | Dòng trống | Python | Tách docstring khỏi import. |
| 8 | Import `settings` | `django.conf.settings` | Dùng để lấy model user đang cấu hình trong project. |
| 9 | Import `models` | `django.db.models` | Đây là API ORM chính của Django để khai báo bảng/cột. |
| 10 | Dòng trống | Python | Tách import khỏi class đầu tiên. |

### Dòng 12-68: `ExperimentRun`

`ExperimentRun` là bảng cha. Mọi dữ liệu khác đều bám vào run này qua `run_id`.

| Dòng | Có gì trong dòng | Dùng gì | Giải thích |
|---:|---|---|---|
| 12 | `class ExperimentRun(models.Model):` | `models.Model` từ Django | Khai báo class ORM. Django sẽ map class này thành bảng DB. |
| 13 | Mở docstring class | Python | Bắt đầu ghi chú cho class. |
| 14 | Mỗi row là một lần chạy | ORM concept | Một dòng trong bảng là một experiment run. |
| 15 | Bảng gốc để liên kết dữ liệu | Database relation | Các bảng config, cycle, metric đều liên kết về bảng này. |
| 16 | Đóng docstring | Python | Kết thúc mô tả class. |
| 17 | Dòng trống | Python | Tách docstring khỏi enum. |
| 18 | `class RunType(models.TextChoices):` | `models.TextChoices` từ Django | Tạo enum dạng text cho field `run_type`. Django dùng để giới hạn lựa chọn. |
| 19 | `OFFLINE_REPLAY = "offline_replay", "Offline Replay"` | TextChoices | Giá trị lưu DB là `offline_replay`, label hiển thị là `Offline Replay`. Đây là kiểu chạy từ CSV/DB replay. |
| 20 | `LIVE = "live", "Live"` | TextChoices | Giá trị lưu DB là `live`, dùng cho dữ liệu sensor gửi realtime. |
| 21 | Dòng trống | Python | Tách enum `RunType` và `Status`. |
| 22 | `class Status(models.TextChoices):` | `models.TextChoices` | Enum trạng thái vòng đời của một run. |
| 23 | `PENDING = "pending", "Pending"` | TextChoices | Run mới tạo, chưa chạy. |
| 24 | `RUNNING = "running", "Running"` | TextChoices | Run đang chạy. |
| 25 | `COMPLETED = "completed", "Completed"` | TextChoices | Run chạy xong thành công. |
| 26 | `FAILED = "failed", "Failed"` | TextChoices | Run lỗi. |
| 27 | `ABORTED = "aborted", "Aborted"` | TextChoices | Run bị dừng thủ công. |
| 28 | Dòng trống | Python | Tách enum khỏi field. |
| 29 | `name = models.CharField(max_length=255)` | `models.CharField` từ Django | Tạo cột chuỗi `name`, tối đa 255 ký tự. Dùng làm tên run trên FE. |
| 30 | `run_type = models.CharField(` | `models.CharField` | Bắt đầu khai báo cột `run_type`. |
| 31 | `max_length=20` | Tham số `CharField` | Cột text tối đa 20 ký tự, đủ chứa `offline_replay` hoặc `live`. |
| 32 | `choices=RunType.choices` | Enum `RunType` | Giới hạn giá trị hợp lệ theo enum ở dòng 18-20. |
| 33 | `default=RunType.OFFLINE_REPLAY` | Enum `RunType` | Nếu không truyền thì mặc định là replay offline. |
| 34 | Đóng khai báo `run_type` | Python | Kết thúc `models.CharField(...)`. |
| 35 | `status = models.CharField(` | `models.CharField` | Bắt đầu khai báo cột trạng thái run. |
| 36 | `max_length=20` | Tham số `CharField` | Độ dài text tối đa. |
| 37 | `choices=Status.choices` | Enum `Status` | Chỉ cho status nằm trong enum dòng 22-27. |
| 38 | `default=Status.PENDING` | Enum `Status` | Run mới mặc định ở trạng thái pending. |
| 39 | Đóng khai báo `status` | Python | Kết thúc field status. |
| 40 | `dataset_source = models.CharField(` | `models.CharField` | Bắt đầu cột mô tả nguồn dữ liệu. |
| 41 | `max_length=512` | Tham số `CharField` | Cho phép lưu path hoặc mô tả query dài hơn tên run. |
| 42 | `null=True` | Tham số field Django | Cho phép DB lưu `NULL`. |
| 43 | `blank=True` | Tham số field Django | Cho phép form/admin/API để trống. Khác với `null`: `blank` là tầng validation. |
| 44 | `help_text=...` | Tham số field Django | Text mô tả cho admin/form/schema. Không ảnh hưởng thuật toán. |
| 45 | Đóng field `dataset_source` | Python | Kết thúc khai báo cột. |
| 46 | `created_at = models.DateTimeField(auto_now_add=True)` | `models.DateTimeField` | Tự ghi thời điểm tạo run. `auto_now_add` là tính năng Django. |
| 47 | `started_at = models.DateTimeField(null=True, blank=True)` | `DateTimeField` | Lưu thời điểm bắt đầu, có thể rỗng khi chưa chạy. |
| 48 | `completed_at = models.DateTimeField(null=True, blank=True)` | `DateTimeField` | Lưu thời điểm kết thúc, có thể rỗng. |
| 49 | `notes = models.TextField(null=True, blank=True)` | `models.TextField` | Cột text dài để ghi chú. |
| 50 | `owner = models.ForeignKey(` | `models.ForeignKey` | Bắt đầu quan hệ nhiều run thuộc về một user. |
| 51 | `settings.AUTH_USER_MODEL` | Django settings | Dùng user model cấu hình trong project, không hard-code `auth.User`. |
| 52 | `on_delete=models.SET_NULL` | Django FK option | Nếu user bị xóa, `owner` của run thành `NULL`, không xóa run. |
| 53 | `null=True` | Field option | DB cho phép owner rỗng. |
| 54 | `blank=True` | Field option | Form/API cho phép không nhập owner. |
| 55 | `related_name="experiment_runs"` | Django relation option | Từ user có thể gọi `user.experiment_runs.all()` để lấy các run của user. |
| 56 | `help_text=...` | Django field option | Mô tả owner dùng cho live ingestion. |
| 57 | Đóng field `owner` | Python | Kết thúc `ForeignKey`. |
| 58 | Dòng trống | Python | Tách field khỏi `Meta`. |
| 59 | `class Meta:` | Django model meta | Khai báo metadata cho model, không phải cột dữ liệu. |
| 60 | `db_table = "experiment_runs"` | Django Meta option | Tên bảng thật trong MySQL là `experiment_runs`. |
| 61 | `indexes = [` | Django index API | Bắt đầu danh sách index để query nhanh hơn. |
| 62 | `models.Index(fields=["status"], ...)` | `models.Index` | Tạo index trên cột `status`, giúp lọc run theo trạng thái nhanh. |
| 63 | `models.Index(fields=["created_at"], ...)` | `models.Index` | Tạo index thời gian tạo, giúp sort/list run mới nhanh. |
| 64 | `models.Index(fields=["owner"], ...)` | `models.Index` | Tạo index owner, giúp lọc run theo user nhanh. |
| 65 | `]` | Python list | Kết thúc danh sách index. |
| 66 | Dòng trống | Python | Tách `Meta` khỏi method. |
| 67 | `def __str__(self) -> str:` | Python method đặc biệt | Django admin/shell dùng method này để hiển thị object dễ đọc. |
| 68 | `return f"Run #{self.pk} ..."` | Python f-string | Trả chuỗi gồm id, tên và status của run. `self.pk` là primary key do Django cung cấp. |

### Dòng 71-126: `ExperimentConfig`

`ExperimentConfig` là snapshot cấu hình. Nó giúp tái lập lại cùng một run, cùng tham số Kalman, ARX, tỷ lệ chia dữ liệu.

| Dòng | Có gì trong dòng | Dùng gì | Giải thích |
|---:|---|---|---|
| 71 | `class ExperimentConfig(models.Model):` | `models.Model` | Tạo model ORM cho bảng config. |
| 72 | Mở docstring | Python | Bắt đầu mô tả class. |
| 73 | Snapshot cấu hình cố định | Concept pipeline | Config được lưu lại tại thời điểm tạo run. |
| 74 | Quan hệ one-to-one với run | DB relation | Mỗi run chỉ có một config. |
| 75 | Mặc định bám ADR-003 | Project decision | Các default như Q, R0, alpha theo quyết định kỹ thuật đã chốt. |
| 76 | Đóng docstring | Python | Kết thúc mô tả class. |
| 77 | Dòng trống | Python | Tách docstring khỏi enum. |
| 78 | `class PreprocessPolicy(models.TextChoices):` | `models.TextChoices` | Enum chính sách xử lý dữ liệu thiếu/lỗi. |
| 79 | `KEEP_LAST = "keep_last", ...` | TextChoices | Khi thiếu dữ liệu thì giữ giá trị hợp lệ gần nhất. |
| 80 | `INTERPOLATE = "interpolate", ...` | TextChoices | Khi thiếu dữ liệu thì nội suy. |
| 81 | `SKIP = "skip", ...` | TextChoices | Khi thiếu dữ liệu thì bỏ qua update. |
| 82 | Dòng trống | Python | Tách enum khỏi quan hệ run. |
| 83 | `run = models.OneToOneField(` | `models.OneToOneField` từ Django | Bắt đầu quan hệ 1-1 với `ExperimentRun`. |
| 84 | `ExperimentRun` | Class trong file này | Model cha được liên kết. |
| 85 | `on_delete=models.CASCADE` | Django relation option | Nếu run bị xóa, config cũng bị xóa theo. |
| 86 | `related_name="config"` | Django relation option | Từ run có thể gọi `run.config`. |
| 87 | Đóng field `run` | Python | Kết thúc quan hệ 1-1. |
| 88 | Dòng trống | Python | Tách nhóm field. |
| 89 | Comment tham số Kalman | Comment Python | Báo các field sau là tham số Kalman. |
| 90 | `x0 = models.FloatField(` | `models.FloatField` | Bắt đầu cột số thực `x0`, trạng thái ban đầu. |
| 91 | `default=0.0` | Field option | Mặc định ban đầu là 0.0 nếu chưa set. |
| 92 | `help_text=...` | Django field option | Mô tả `x0` là estimate ban đầu. |
| 93 | Đóng field `x0` | Python | Kết thúc khai báo. |
| 94 | `P0 = models.FloatField(...)` | `FloatField` | Hiệp phương sai ban đầu của Kalman. |
| 95 | `Q = models.FloatField(...)` | `FloatField` | Nhiễu quá trình, thường tune bằng validation. |
| 96 | `R0 = models.FloatField(...)` | `FloatField` | Nhiễu đo lường ban đầu. |
| 97 | `R_min = models.FloatField(...)` | `FloatField` | Cận dưới của R thích nghi. |
| 98 | `R_max = models.FloatField(...)` | `FloatField` | Cận trên của R thích nghi. |
| 99 | `alpha = models.FloatField(...)` | `FloatField` | Hệ số EMA làm mượt R thích nghi. |
| 100 | Dòng trống | Python | Tách nhóm Kalman khỏi split ratio. |
| 101 | Comment tỷ lệ chia dữ liệu | Comment Python | Các field sau là tỷ lệ train/val/test theo thời gian. |
| 102 | `train_ratio = models.FloatField(default=0.60)` | `FloatField` | 60% dữ liệu đầu dùng train. |
| 103 | `val_ratio = models.FloatField(default=0.20)` | `FloatField` | 20% tiếp theo dùng validation. |
| 104 | `test_ratio = models.FloatField(default=0.20)` | `FloatField` | 20% cuối dùng test. |
| 105 | Dòng trống | Python | Tách nhóm tỷ lệ khỏi ARX. |
| 106 | Comment bậc ARX | Comment Python | Các field sau định nghĩa order của model ARX. |
| 107 | `arx_na = models.IntegerField(...)` | `models.IntegerField` | Số lag output, tức bậc autoregressive. |
| 108 | `arx_nb = models.IntegerField(...)` | `IntegerField` | Số lag input ngoại sinh. |
| 109 | `arx_nk = models.IntegerField(...)` | `IntegerField` | Độ trễ input. |
| 110 | Dòng trống | Python | Tách ARX khỏi preprocess policy. |
| 111 | `preprocessing_policy = models.CharField(` | `CharField` | Bắt đầu field lưu chính sách tiền xử lý. |
| 112 | `max_length=20` | Field option | Độ dài text tối đa. |
| 113 | `choices=PreprocessPolicy.choices` | Enum dòng 78-81 | Chỉ cho phép 3 policy đã định nghĩa. |
| 114 | `default=PreprocessPolicy.KEEP_LAST` | Enum | Mặc định dùng keep_last. |
| 115 | Đóng field `preprocessing_policy` | Python | Kết thúc khai báo. |
| 116 | Dòng trống | Python | Tách nhóm field. |
| 117 | Comment snapshot JSON | Comment Python | Báo field sau lưu JSON đầy đủ của config. |
| 118 | `raw_config_json = models.TextField(default="{}")` | `TextField` | Lưu toàn bộ config dạng JSON string. |
| 119 | Dòng trống | Python | Tách field khỏi timestamp. |
| 120 | `created_at = models.DateTimeField(auto_now_add=True)` | `DateTimeField` | Tự ghi thời điểm tạo config. |
| 121 | Dòng trống | Python | Tách field khỏi `Meta`. |
| 122 | `class Meta:` | Django Meta | Bắt đầu metadata cho model. |
| 123 | `db_table = "experiment_configs"` | Django Meta option | Tên bảng DB thật. |
| 124 | Dòng trống | Python | Tách `Meta` khỏi method. |
| 125 | `def __str__(self) -> str:` | Python method | Chuỗi đại diện object. |
| 126 | `return f"Config for Run #{self.run_id}"` | f-string, Django FK id | `run_id` là cột FK tự tạo từ `run`. |

### Dòng 129-175: `ARXArtifact`

`ARXArtifact` lưu model ARX sau khi train. Nó không phải Kalman, nhưng Kalman dùng dự đoán ARX làm prior nếu adapter có artifact.

| Dòng | Có gì trong dòng | Dùng gì | Giải thích |
|---:|---|---|---|
| 129 | `class ARXArtifact(models.Model):` | `models.Model` | Tạo bảng lưu artifact ARX. |
| 130 | Mở docstring | Python | Bắt đầu mô tả class. |
| 131 | Hệ số model ARX và hiệu năng | Concept ML | Lưu tham số đã train và metric. |
| 132 | One-to-one với run | DB relation | Mỗi run có tối đa một artifact ARX. |
| 133 | Đóng docstring | Python | Kết thúc mô tả. |
| 134 | Dòng trống | Python | Tách docstring khỏi field. |
| 135 | `run = models.OneToOneField(` | `OneToOneField` | Bắt đầu liên kết artifact với run. |
| 136 | `ExperimentRun` | Class trong file | Bảng cha. |
| 137 | `on_delete=models.CASCADE` | Django relation option | Xóa run thì artifact bị xóa theo. |
| 138 | `related_name="arx_artifact"` | Django relation option | Từ run gọi `run.arx_artifact`. |
| 139 | Đóng field `run` | Python | Kết thúc quan hệ. |
| 140 | Dòng trống | Python | Tách nhóm. |
| 141 | Comment bậc ARX | Comment | Các field sau là order ARX khi train. |
| 142 | `na = models.IntegerField()` | `IntegerField` | Lưu bậc output lag. |
| 143 | `nb = models.IntegerField()` | `IntegerField` | Lưu bậc input lag. |
| 144 | `nk = models.IntegerField()` | `IntegerField` | Lưu input delay. |
| 145 | Dòng trống | Python | Tách nhóm. |
| 146 | Comment nguồn dữ liệu train | Comment | Các field sau mô tả tập train. |
| 147 | `n_train_samples = models.IntegerField()` | `IntegerField` | Số sample dùng để train ARX. |
| 148 | `train_start_ts = models.DateTimeField()` | `DateTimeField` | Timestamp bắt đầu tập train. |
| 149 | `train_end_ts = models.DateTimeField()` | `DateTimeField` | Timestamp kết thúc tập train. |
| 150 | Dòng trống | Python | Tách nhóm. |
| 151 | Comment model serialize | Comment | Các field sau chứa model dưới dạng text/JSON. |
| 152 | `coefficients_json = models.TextField(` | `TextField` | Bắt đầu cột lưu vector hệ số theta dưới dạng JSON. |
| 153 | `help_text=...` | Django field option | Mô tả cột là JSON array của hệ số. |
| 154 | Đóng field `coefficients_json` | Python | Kết thúc khai báo. |
| 155 | `input_cols_json = models.TextField(` | `TextField` | Bắt đầu cột lưu danh sách input column. |
| 156 | `help_text=...` | Django field option | Mô tả cột là JSON array tên input. |
| 157 | Đóng field `input_cols_json` | Python | Kết thúc khai báo. |
| 158 | `output_col = models.CharField(...)` | `CharField` | Lưu tên cột output, mặc định `Soil_Moisture`. |
| 159 | Dòng trống | Python | Tách nhóm. |
| 160 | Comment metric train/validation | Comment | Các field sau lưu lỗi model ARX. |
| 161 | `rmse_train = models.FloatField(null=True, blank=True)` | `FloatField` | RMSE trên train, có thể rỗng. |
| 162 | `rmse_val = models.FloatField(null=True, blank=True)` | `FloatField` | RMSE trên validation, có thể rỗng. |
| 163 | `mae_train = models.FloatField(null=True, blank=True)` | `FloatField` | MAE trên train. |
| 164 | `mae_val = models.FloatField(null=True, blank=True)` | `FloatField` | MAE trên validation. |
| 165 | Dòng trống | Python | Tách nhóm. |
| 166 | Comment đường dẫn artifact | Comment | Field sau lưu path file JSON nếu có. |
| 167 | `artifact_path = models.CharField(...)` | `CharField` | Đường dẫn file artifact, có thể `NULL`. |
| 168 | Dòng trống | Python | Tách field khỏi timestamp. |
| 169 | `created_at = models.DateTimeField(auto_now_add=True)` | `DateTimeField` | Tự lưu thời điểm tạo artifact. |
| 170 | Dòng trống | Python | Tách timestamp khỏi `Meta`. |
| 171 | `class Meta:` | Django Meta | Metadata model. |
| 172 | `db_table = "arx_artifacts"` | Meta option | Tên bảng DB. |
| 173 | Dòng trống | Python | Tách Meta khỏi method. |
| 174 | `def __str__(self) -> str:` | Python method | Chuỗi đại diện object. |
| 175 | `return f"ARX({self.na},...)..."` | f-string | Hiển thị order ARX và run_id. |

### Dòng 178-343: `PipelineCycle`

Đây là bảng quan trọng nhất khi xem luồng xử lý. Mỗi dòng là một cycle, tức một timestamp/sample đã đi qua raw -> preprocess -> ARX predict -> Kalman filter -> lưu kết quả.

| Dòng | Có gì trong dòng | Dùng gì | Giải thích |
|---:|---|---|---|
| 178 | `class PipelineCycle(models.Model):` | `models.Model` | Tạo model ORM cho bảng cycle. |
| 179-184 | Docstring class | Python docstring | Giải thích mỗi row là một timestep đã xử lý và có thể truy vết raw, ARX, Kalman. |
| 185 | Dòng trống | Python | Tách docstring khỏi field. |
| 186 | Comment `BigAutoField` | Comment | Giải thích vì sao khai báo id tường minh. |
| 187 | `id = models.BigAutoField(primary_key=True)` | `models.BigAutoField` | Primary key kiểu số lớn, tự tăng. Django cung cấp field này. |
| 188 | Dòng trống | Python | Tách id khỏi enum. |
| 189 | `class SliceType(models.TextChoices):` | `TextChoices` | Enum cho tập dữ liệu: train/validation/test. |
| 190 | `TRAIN = "train", "Train"` | TextChoices | Dòng cycle thuộc tập train. |
| 191 | `VALIDATION = "validation", "Validation"` | TextChoices | Dòng cycle thuộc tập validation. |
| 192 | `TEST = "test", "Test"` | TextChoices | Dòng cycle thuộc tập test. |
| 193 | Dòng trống | Python | Tách enum. |
| 194 | `class SourceType(models.TextChoices):` | `TextChoices` | Enum nguồn dữ liệu. |
| 195 | `CSV_REPLAY = "csv_replay", ...` | TextChoices | Dữ liệu chạy lại từ CSV. |
| 196 | `MYSQL_REPLAY = "mysql_replay", ...` | TextChoices | Dữ liệu replay từ MySQL. |
| 197 | `LIVE = "live", ...` | TextChoices | Dữ liệu live từ sensor/API. |
| 198 | Dòng trống | Python | Tách enum. |
| 199 | `class CycleStatus(models.TextChoices):` | `TextChoices` | Enum kết quả xử lý của cycle. |
| 200 | `OK = "ok", "OK"` | TextChoices | Cycle xử lý bình thường. |
| 201 | `SKIPPED_NO_MEASUREMENT = ...` | TextChoices | Không có đo lường nên bỏ cập nhật Kalman. |
| 202 | `SKIPPED_INVALID = ...` | TextChoices | Sample invalid nên bỏ qua. |
| 203 | `ERROR = "error", "Error"` | TextChoices | Cycle bị lỗi. |
| 204 | Dòng trống | Python | Tách enum. |
| 205 | `class PreprocessStatus(models.TextChoices):` | `TextChoices` | Enum trạng thái sau tiền xử lý. |
| 206 | `VALID = "valid", "Valid"` | TextChoices | Dữ liệu hợp lệ. |
| 207 | `INTERPOLATED = ...` | TextChoices | Dữ liệu được nội suy. |
| 208 | `KEPT_LAST = ...` | TextChoices | Dữ liệu dùng giá trị hợp lệ gần nhất. |
| 209 | `SKIPPED = ...` | TextChoices | Dữ liệu bị skip. |
| 210 | `INVALID = ...` | TextChoices | Dữ liệu không hợp lệ. |
| 211 | Dòng trống | Python | Tách enum. |
| 212 | `class AdaptiveStatus(models.TextChoices):` | `TextChoices` | Enum trạng thái cập nhật R thích nghi. |
| 213 | `R_UPDATED = "R_updated", ...` | TextChoices | R được cập nhật ở cycle này. |
| 214 | `R_SKIPPED = "R_skipped", ...` | TextChoices | Không cập nhật R vì không có measurement. |
| 215 | `SKIPPED = "skipped", ...` | TextChoices | Nhánh lỗi, adaptive bị bỏ qua. |
| 216 | Dòng trống | Python | Tách enum khỏi field. |
| 217 | `run = models.ForeignKey(` | `ForeignKey` | Bắt đầu quan hệ nhiều cycle thuộc một run. |
| 218 | `ExperimentRun` | Class trong file | Model cha. |
| 219 | `on_delete=models.CASCADE` | Relation option | Xóa run thì xóa các cycle của run đó. |
| 220 | `related_name="cycles"` | Relation option | Từ run gọi `run.cycles.all()`. |
| 221 | Đóng field `run` | Python | Kết thúc FK. |
| 222 | `sample_ts = models.DateTimeField(...)` | `DateTimeField` | Timestamp gốc của sample. |
| 223 | `cycle_index = models.IntegerField(...)` | `IntegerField` | Thứ tự cycle trong run, bắt đầu từ 0. |
| 224 | `slice_type = models.CharField(...)` | `CharField` + `SliceType.choices` | Lưu sample thuộc train/validation/test. |
| 225 | `source_type = models.CharField(` | `CharField` | Bắt đầu field nguồn dữ liệu. |
| 226 | `max_length=20` | Field option | Độ dài tối đa. |
| 227 | `choices=SourceType.choices` | Enum `SourceType` | Chỉ nhận nguồn đã định nghĩa. |
| 228 | `default=SourceType.CSV_REPLAY` | Enum | Mặc định là CSV replay. |
| 229 | Đóng field `source_type` | Python | Kết thúc khai báo nguồn. |
| 230 | Dòng trống | Python | Tách nhóm. |
| 231 | Comment dữ liệu thô | Comment | Các field sau là raw sensor. |
| 232 | `raw_soil_moisture = models.FloatField(...)` | `FloatField` | Soil moisture thô. Có thể null nếu thiếu. |
| 233 | `raw_temperature = models.FloatField(...)` | `FloatField` | Nhiệt độ thô. |
| 234 | `raw_humidity = models.FloatField(...)` | `FloatField` | Độ ẩm không khí thô. |
| 235 | `raw_light = models.FloatField(...)` | `FloatField` | Ánh sáng thô. |
| 236 | `raw_drip = models.FloatField(...)` | `FloatField` | Trạng thái/tín hiệu drip thô. |
| 237 | `raw_mist = models.FloatField(...)` | `FloatField` | Trạng thái/tín hiệu mist thô. |
| 238 | `raw_fan = models.FloatField(...)` | `FloatField` | Trạng thái/tín hiệu fan thô. |
| 239 | Dòng trống | Python | Tách raw khỏi preprocess. |
| 240 | Comment trạng thái tiền xử lý | Comment | Field sau cho biết raw được xử lý ra sao. |
| 241 | `preprocess_status = models.CharField(` | `CharField` | Bắt đầu field trạng thái preprocess. |
| 242 | `max_length=20` | Field option | Độ dài tối đa. |
| 243 | `choices=PreprocessStatus.choices` | Enum dòng 205-210 | Giới hạn status hợp lệ. |
| 244 | `default=PreprocessStatus.VALID` | Enum | Mặc định là valid. |
| 245 | Đóng field `preprocess_status` | Python | Kết thúc field. |
| 246 | Dòng trống | Python | Tách preprocess khỏi ARX. |
| 247 | Comment dự đoán ARX | Comment | Field sau là output của ARX. |
| 248 | `arx_predicted = models.FloatField(` | `FloatField` | Bắt đầu cột dự đoán ARX. |
| 249 | `null=True` | Field option | DB cho phép null nếu ARX không dự đoán được. |
| 250 | `blank=True` | Field option | Form/API cho phép trống. |
| 251 | `help_text=...` | Field option | Mô tả đây là dự đoán Soil_Moisture bước kế tiếp. |
| 252 | Đóng field `arx_predicted` | Python | Kết thúc khai báo. |
| 253 | Dòng trống | Python | Tách ARX khỏi Kalman. |
| 254 | Comment thông số Kalman | Comment | Các field sau là biến nội bộ của Kalman filter. |
| 255 | `kf_x_prior = models.FloatField(...)` | `FloatField` | Prior estimate trước khi update bằng measurement. |
| 256 | `kf_P_prior = models.FloatField(...)` | `FloatField` | Prior covariance trước update. |
| 257 | `kf_innovation = models.FloatField(...)` | `FloatField` | Sai lệch `e_k = z_k - x^-_k`. |
| 258 | `kf_R = models.FloatField(...)` | `FloatField` | R thích nghi tại cycle này. |
| 259 | `kf_K = models.FloatField(...)` | `FloatField` | Kalman gain tại cycle này. |
| 260 | `kf_x_posterior = models.FloatField(...)` | `FloatField` | Giá trị Soil_Moisture sau lọc Kalman. Đây là filtered. |
| 261 | `kf_P_posterior = models.FloatField(...)` | `FloatField` | Covariance sau update. |
| 262 | Dòng trống | Python | Tách Kalman khỏi adaptive status. |
| 263 | Comment adaptive estimator | Comment | Field sau cho biết R có được update không. |
| 264 | `adaptive_status = models.CharField(` | `CharField` | Bắt đầu field trạng thái adaptive. |
| 265 | `max_length=20` | Field option | Độ dài tối đa. |
| 266 | `choices=AdaptiveStatus.choices` | Enum dòng 212-215 | Chỉ nhận status adaptive hợp lệ. |
| 267 | `default=AdaptiveStatus.R_UPDATED` | Enum | Mặc định là R được update. |
| 268 | `help_text=...` | Field option | Mô tả field. |
| 269 | Đóng field `adaptive_status` | Python | Kết thúc field. |
| 270 | Dòng trống | Python | Tách adaptive khỏi cycle outcome. |
| 271 | Comment kết quả xử lý cycle | Comment | Các field sau là kết quả tổng quát của cycle. |
| 272 | `cycle_status = models.CharField(` | `CharField` | Bắt đầu field trạng thái cycle. |
| 273 | `max_length=30` | Field option | Dài hơn vì `skipped_no_measurement` nhiều ký tự. |
| 274 | `choices=CycleStatus.choices` | Enum dòng 199-203 | Chỉ nhận status cycle hợp lệ. |
| 275 | `default=CycleStatus.OK` | Enum | Mặc định là ok. |
| 276 | Đóng field `cycle_status` | Python | Kết thúc field. |
| 277 | `error_message = models.CharField(...)` | `CharField` | Lưu message nếu cycle lỗi, có thể null. |
| 278 | Dòng trống | Python | Tách outcome khỏi performance. |
| 279 | Comment hiệu năng xử lý | Comment | Field sau lưu thời gian xử lý. |
| 280 | `latency_ms = models.FloatField(` | `FloatField` | Bắt đầu field latency. |
| 281 | `null=True` | Field option | Cho phép null. |
| 282 | `blank=True` | Field option | Cho phép trống ở form/API. |
| 283 | `help_text=...` | Field option | Mô tả latency tính bằng milliseconds. |
| 284 | Đóng field `latency_ms` | Python | Kết thúc field. |
| 285 | Dòng trống | Python | Tách latency khỏi timestamp tạo dòng. |
| 286 | `created_at = models.DateTimeField(auto_now_add=True)` | `DateTimeField` | Tự lưu thời điểm cycle được ghi vào DB. |
| 287 | Dòng trống | Python | Tách field khỏi dedupe. |
| 288 | Comment dedupe MySQL | Comment | Giải thích vì MySQL partial unique index không ổn định nên dùng key chuỗi. |
| 289 | Comment tiếp dedupe | Comment | Nhắc constraint nằm trong `Meta.constraints`. |
| 290 | `ingest_dedupe_key = models.CharField(` | `CharField` | Bắt đầu field khóa chống ghi trùng. |
| 291 | `max_length=191` | Field option | Độ dài an toàn với index MySQL utf8mb4. |
| 292 | `help_text=(` | Field option | Bắt đầu mô tả nhiều dòng. |
| 293 | Chuỗi mô tả live key | String Python | Với live, key dựa trên run + UTC timestamp. |
| 294 | Chuỗi mô tả replay key | String Python | Với replay, key dựa trên run + cycle_index. |
| 295 | Đóng `help_text` | Python | Kết thúc chuỗi mô tả. |
| 296 | Đóng field `ingest_dedupe_key` | Python | Kết thúc field. |
| 297 | Dòng trống | Python | Tách field khỏi `Meta`. |
| 298 | `class Meta:` | Django Meta | Bắt đầu metadata bảng cycle. |
| 299 | `db_table = "pipeline_cycles"` | Meta option | Tên bảng thật. |
| 300 | `constraints = [` | Django constraints | Bắt đầu danh sách ràng buộc DB. |
| 301 | `models.UniqueConstraint(` | `UniqueConstraint` từ Django | Bắt đầu constraint unique. |
| 302 | `fields=["run", "cycle_index"]` | Constraint option | Một run không được có hai cycle cùng index. |
| 303 | `name="uq_cycles_run_index"` | Constraint option | Tên constraint trong DB. |
| 304 | Đóng unique constraint | Python | Kết thúc constraint đầu. |
| 305 | `models.UniqueConstraint(` | `UniqueConstraint` | Bắt đầu unique constraint dedupe. |
| 306 | `fields=["run", "ingest_dedupe_key"]` | Constraint option | Một run không được ghi trùng dedupe key. |
| 307 | `name="uq_cycles_run_ingest_dedupe"` | Constraint option | Tên constraint. |
| 308 | Đóng unique constraint | Python | Kết thúc constraint. |
| 309 | `models.CheckConstraint(` | `CheckConstraint` từ Django | Bắt đầu constraint kiểm tra giá trị hợp lệ. |
| 310 | `check=models.Q(slice_type__in=[...])` | `models.Q` từ Django | Điều kiện DB: `slice_type` chỉ được là train/validation/test. |
| 311 | `name="chk_cycles_slice_type"` | Constraint option | Tên check constraint. |
| 312 | Đóng check constraint | Python | Kết thúc check. |
| 313 | `models.CheckConstraint(` | `CheckConstraint` | Bắt đầu check cho source_type. |
| 314 | `check=models.Q(source_type__in=[...])` | `models.Q` | Chỉ cho source_type thuộc csv_replay/mysql_replay/live. |
| 315 | `name="chk_cycles_source_type"` | Constraint option | Tên check. |
| 316 | Đóng check constraint | Python | Kết thúc check. |
| 317 | `models.CheckConstraint(` | `CheckConstraint` | Bắt đầu check preprocess_status. |
| 318 | `check=models.Q(` | `models.Q` | Bắt đầu điều kiện Q nhiều dòng. |
| 319 | `preprocess_status__in=[...]` | Django lookup `__in` | Field preprocess_status phải nằm trong list hợp lệ. |
| 320 | Đóng `models.Q(...)` | Python | Kết thúc điều kiện Q. |
| 321 | `name="chk_cycles_preprocess_status"` | Constraint option | Tên check. |
| 322 | Đóng check constraint | Python | Kết thúc check. |
| 323 | `models.CheckConstraint(` | `CheckConstraint` | Bắt đầu check adaptive_status. |
| 324 | `check=models.Q(` | `models.Q` | Bắt đầu điều kiện Q. |
| 325 | `adaptive_status__in=[...]` | Django lookup `__in` | Chỉ nhận R_updated/R_skipped/skipped. |
| 326 | Đóng Q | Python | Kết thúc điều kiện. |
| 327 | `name="chk_cycles_adaptive_status"` | Constraint option | Tên check. |
| 328 | Đóng check constraint | Python | Kết thúc check. |
| 329 | `models.CheckConstraint(` | `CheckConstraint` | Bắt đầu check cycle_status. |
| 330 | `check=models.Q(` | `models.Q` | Bắt đầu điều kiện Q. |
| 331 | `cycle_status__in=[...]` | Django lookup `__in` | Chỉ nhận ok/skipped/error status đã định nghĩa. |
| 332 | Đóng Q | Python | Kết thúc điều kiện. |
| 333 | `name="chk_cycles_cycle_status"` | Constraint option | Tên check. |
| 334 | Đóng check constraint | Python | Kết thúc check. |
| 335 | `]` | Python list | Kết thúc danh sách constraints. |
| 336 | `indexes = [` | Django Index API | Bắt đầu danh sách index. |
| 337 | `models.Index(fields=["run", "sample_ts"], ...)` | `models.Index` | Tăng tốc query cycle theo run và timestamp. |
| 338 | `models.Index(fields=["run", "slice_type"], ...)` | `models.Index` | Tăng tốc query theo run và slice. |
| 339 | `]` | Python list | Kết thúc danh sách index. |
| 340 | `ordering = ["run", "cycle_index"]` | Django Meta option | Query mặc định sort theo run rồi cycle_index. |
| 341 | Dòng trống | Python | Tách Meta khỏi method. |
| 342 | `def __str__(self) -> str:` | Python method đặc biệt | Chuỗi đại diện cycle. |
| 343 | `return f"Cycle #{...}"` | f-string | Hiển thị index, timestamp và status của cycle. |

### Dòng 346-484: `EvaluationSummary`

`EvaluationSummary` lưu metric tổng hợp sau khi pipeline chạy xong. Đây là bảng mà FE đang đọc để show các thông số Train, Validation, Test.

| Dòng | Có gì trong dòng | Dùng gì | Giải thích |
|---:|---|---|---|
| 346 | `class EvaluationSummary(models.Model):` | `models.Model` | Tạo model ORM cho bảng metric tổng hợp. |
| 347-351 | Docstring class | Python docstring | Nói metric được tổng hợp theo run và data slice, trong đó test là acceptance gate chính thức. |
| 352 | Dòng trống | Python | Tách docstring khỏi enum. |
| 353 | `class SliceType(models.TextChoices):` | `TextChoices` | Enum slice cho summary. |
| 354 | `TRAIN = "train", "Train"` | TextChoices | Metric của train slice. |
| 355 | `VALIDATION = "validation", "Validation"` | TextChoices | Metric của validation slice. |
| 356 | `TEST = "test", "Test"` | TextChoices | Metric của test slice. |
| 357 | Dòng trống | Python | Tách enum khỏi field. |
| 358 | `run = models.ForeignKey(` | `ForeignKey` | Bắt đầu quan hệ nhiều summary thuộc một run. |
| 359 | `ExperimentRun` | Class trong file | Bảng cha. |
| 360 | `on_delete=models.CASCADE` | Relation option | Xóa run thì xóa summary theo. |
| 361 | `related_name="evaluation_summaries"` | Relation option | Từ run gọi `run.evaluation_summaries.all()`. |
| 362 | Đóng field `run` | Python | Kết thúc FK. |
| 363 | `slice_type = models.CharField(...)` | `CharField` + `SliceType.choices` | Lưu summary này thuộc train/validation/test. |
| 364 | Dòng trống | Python | Tách nhóm. |
| 365 | Comment số lượng sample | Comment | Các field sau là count. |
| 366 | `n_samples = models.IntegerField(default=0)` | `IntegerField` | Tổng số sample/cycle trong slice. |
| 367 | `n_valid = models.IntegerField(default=0)` | `IntegerField` | Số cycle xử lý ok. |
| 368 | `n_skipped = models.IntegerField(default=0)` | `IntegerField` | Số cycle bị skip. |
| 369 | `n_error = models.IntegerField(default=0)` | `IntegerField` | Số cycle lỗi. |
| 370 | Dòng trống | Python | Tách count khỏi accuracy. |
| 371 | Comment độ chính xác ARX | Comment | Các field sau là metric ARX. |
| 372 | `rmse_arx = models.FloatField(null=True, blank=True)` | `FloatField` | RMSE của ARX so với raw/reference. |
| 373 | `mae_arx = models.FloatField(null=True, blank=True)` | `FloatField` | MAE của ARX. |
| 374 | Dòng trống | Python | Tách ARX khỏi Kalman. |
| 375 | Comment độ chính xác Kalman | Comment | Các field sau là metric filtered. |
| 376 | `rmse_filtered = models.FloatField(...)` | `FloatField` | RMSE của output sau Kalman. |
| 377 | `mae_filtered = models.FloatField(...)` | `FloatField` | MAE của output sau Kalman. |
| 378 | Dòng trống | Python | Tách accuracy khỏi guardrail. |
| 379 | Comment metric ADR-003 | Comment | Các field sau dùng để pass/fail theo ngưỡng. |
| 380 | `var_diff_raw = models.FloatField(` | `FloatField` | Bắt đầu field phương sai sai phân của raw. |
| 381 | `null=True, blank=True` | Field option | Cho phép rỗng nếu không đủ dữ liệu. |
| 382 | `help_text="var(diff(raw_soil_moisture))"` | Field option | Công thức: variance của độ thay đổi raw. |
| 383 | Đóng field `var_diff_raw` | Python | Kết thúc field. |
| 384 | `var_diff_filtered = models.FloatField(` | `FloatField` | Bắt đầu field phương sai sai phân của filtered. |
| 385 | `null=True, blank=True` | Field option | Cho phép rỗng. |
| 386 | `help_text="var(diff(kf_x_posterior))"` | Field option | Công thức dùng output Kalman. |
| 387 | Đóng field `var_diff_filtered` | Python | Kết thúc field. |
| 388 | `variance_reduction = models.FloatField(` | `FloatField` | Bắt đầu field mức giảm phương sai. |
| 389 | `null=True, blank=True` | Field option | Cho phép rỗng. |
| 390 | `help_text=...` | Field option | Công thức `1 - var_diff_filtered / var_diff_raw`, test cần >= 0.20. |
| 391 | Đóng field `variance_reduction` | Python | Kết thúc field. |
| 392 | `rmse_ratio = models.FloatField(` | `FloatField` | Tỷ lệ RMSE filtered / RMSE ARX. |
| 393 | `null=True, blank=True` | Field option | Cho phép rỗng nếu thiếu metric. |
| 394 | `help_text=...` | Field option | Test cần tỷ lệ <= 1.05. |
| 395 | Đóng field `rmse_ratio` | Python | Kết thúc field. |
| 396 | `mae_ratio = models.FloatField(` | `FloatField` | Tỷ lệ MAE filtered / MAE ARX. |
| 397 | `null=True, blank=True` | Field option | Cho phép rỗng. |
| 398 | `help_text=...` | Field option | Test cần tỷ lệ <= 1.05. |
| 399 | Đóng field `mae_ratio` | Python | Kết thúc field. |
| 400 | Dòng trống | Python | Tách guardrail khỏi adaptive count. |
| 401 | Comment phân bố adaptive | Comment | Các field sau đếm trạng thái R. |
| 402 | `n_r_updated = models.IntegerField(` | `IntegerField` | Bắt đầu field đếm số cycle R_updated. |
| 403 | `default=0` | Field option | Mặc định 0. |
| 404 | `help_text=...` | Field option | Mô tả số cycle update R. |
| 405 | Đóng field `n_r_updated` | Python | Kết thúc field. |
| 406 | `n_r_skipped = models.IntegerField(` | `IntegerField` | Bắt đầu field đếm R_skipped. |
| 407 | `default=0` | Field option | Mặc định 0. |
| 408 | `help_text=...` | Field option | Mô tả số cycle bỏ update R do không có measurement. |
| 409 | Đóng field `n_r_skipped` | Python | Kết thúc field. |
| 410 | `n_adaptive_skipped = models.IntegerField(` | `IntegerField` | Bắt đầu field đếm nhánh adaptive skipped. |
| 411 | `default=0` | Field option | Mặc định 0. |
| 412 | `help_text=...` | Field option | Mô tả số cycle đi nhánh lỗi. |
| 413 | Đóng field `n_adaptive_skipped` | Python | Kết thúc field. |
| 414 | Dòng trống | Python | Tách adaptive count khỏi latency. |
| 415 | Comment độ trễ | Comment | Các field sau là latency. |
| 416 | `latency_mean_ms = models.FloatField(` | `FloatField` | Bắt đầu field latency trung bình. |
| 417 | `null=True` | Field option | Cho phép null. |
| 418 | `blank=True` | Field option | Cho phép trống. |
| 419 | `help_text=...` | Field option | Mô tả thời gian trung bình mỗi bước. |
| 420 | Đóng field `latency_mean_ms` | Python | Kết thúc field. |
| 421 | `latency_p95_ms = models.FloatField(` | `FloatField` | Bắt đầu field latency percentile 95. |
| 422 | `null=True` | Field option | Cho phép null. |
| 423 | `blank=True` | Field option | Cho phép trống. |
| 424 | `help_text=...` | Field option | Mô tả p95 latency. |
| 425 | Đóng field `latency_p95_ms` | Python | Kết thúc field. |
| 426 | Dòng trống | Python | Tách latency khỏi diagnostics. |
| 427 | Comment chẩn đoán | Comment | Các field sau là thống kê innovation, R, P. |
| 428 | `innovation_mean = models.FloatField(...)` | `FloatField` | Trung bình innovation. |
| 429 | `innovation_std = models.FloatField(...)` | `FloatField` | Độ lệch chuẩn innovation. |
| 430 | `innovation_max_abs = models.FloatField(...)` | `FloatField` | Innovation lớn nhất theo trị tuyệt đối. |
| 431 | `R_mean = models.FloatField(...)` | `FloatField` | Trung bình R. |
| 432 | `R_min_observed = models.FloatField(...)` | `FloatField` | R nhỏ nhất quan sát được. |
| 433 | `R_max_observed = models.FloatField(...)` | `FloatField` | R lớn nhất quan sát được. |
| 434 | `P_mean = models.FloatField(...)` | `FloatField` | Trung bình posterior covariance P. |
| 435 | `P_max = models.FloatField(...)` | `FloatField` | P lớn nhất. |
| 436 | Dòng trống | Python | Tách diagnostics khỏi cờ pass/fail. |
| 437 | Comment cờ pass/fail | Comment | Các field sau lưu kết quả đạt/ngưỡng. |
| 438 | `pass_variance_reduction = models.BooleanField(` | `BooleanField` | Cờ variance_reduction có pass không. |
| 439 | `null=True, blank=True` | Field option | Cho phép chưa biết nếu thiếu dữ liệu. |
| 440 | `help_text=...` | Field option | True nếu variance_reduction >= 0.20. |
| 441 | Đóng field `pass_variance_reduction` | Python | Kết thúc field. |
| 442 | `pass_rmse_guardrail = models.BooleanField(` | `BooleanField` | Cờ RMSE ratio có pass không. |
| 443 | `null=True, blank=True` | Field option | Cho phép chưa biết. |
| 444 | `help_text=...` | Field option | True nếu rmse_ratio <= 1.05. |
| 445 | Đóng field `pass_rmse_guardrail` | Python | Kết thúc field. |
| 446 | `pass_mae_guardrail = models.BooleanField(` | `BooleanField` | Cờ MAE ratio có pass không. |
| 447 | `null=True, blank=True` | Field option | Cho phép chưa biết. |
| 448 | `help_text=...` | Field option | True nếu mae_ratio <= 1.05. |
| 449 | Đóng field `pass_mae_guardrail` | Python | Kết thúc field. |
| 450 | Dòng trống | Python | Tách pass/fail khỏi timestamp. |
| 451 | `created_at = models.DateTimeField(auto_now_add=True)` | `DateTimeField` | Tự ghi thời điểm tạo summary. |
| 452 | Dòng trống | Python | Tách field khỏi Meta. |
| 453 | `class Meta:` | Django Meta | Bắt đầu metadata model. |
| 454 | `db_table = "evaluation_summaries"` | Meta option | Tên bảng thật. |
| 455 | `unique_together = [("run", "slice_type")]` | Django Meta option | Mỗi run chỉ có một summary cho mỗi slice. |
| 456 | Dòng trống | Python | Tách Meta khỏi method. |
| 457 | `def __str__(self) -> str:` | Python method đặc biệt | Chuỗi đại diện object. |
| 458 | `return f"Eval [{...}]"` | f-string | Hiển thị slice và run_id. |
| 459 | Dòng trống | Python | Tách method khỏi property. |
| 460 | `@property` | Decorator Python mặc định | Biến method ngay dưới thành thuộc tính đọc như field. |
| 461 | `def cycle_success_rate(...)` | Python method | Tính tỷ lệ cycle ok. Không lưu DB, tính động khi gọi. |
| 462 | Docstring property | Python docstring | Công thức `n_valid / n_samples`. |
| 463 | `if self.n_samples == 0:` | Python điều kiện | Tránh chia cho 0. |
| 464 | `return None` | Python | Nếu không có sample thì không tính được. |
| 465 | `return self.n_valid / self.n_samples` | Python arithmetic | Trả tỷ lệ success. |
| 466 | Dòng trống | Python | Tách property. |
| 467 | `@property` | Decorator Python | Tạo property thứ hai. |
| 468 | `def sample_loss_rate(...)` | Python method | Tính tỷ lệ sample bị skip hoặc lỗi. |
| 469 | Docstring property | Python docstring | Công thức `(n_skipped + n_error) / n_samples`. |
| 470 | `if self.n_samples == 0:` | Python điều kiện | Tránh chia cho 0. |
| 471 | `return None` | Python | Không có sample thì không tính. |
| 472 | `return (self.n_skipped + self.n_error) / self.n_samples` | Python arithmetic | Tính loss rate. |
| 473 | Dòng trống | Python | Tách property. |
| 474 | `@property` | Decorator Python | Tạo property thứ ba. |
| 475 | `def passes_acceptance_gate(...)` | Python method | Tính tổng hợp xem có pass toàn bộ gate không. |
| 476 | Docstring property | Python docstring | True nếu cả 3 tiêu chí ADR-003 đều pass, None nếu thiếu flag. |
| 477 | `flags = (` | Python tuple | Bắt đầu tuple chứa 3 cờ pass/fail. |
| 478 | `self.pass_variance_reduction` | Model field | Cờ pass variance reduction. |
| 479 | `self.pass_rmse_guardrail` | Model field | Cờ pass RMSE ratio. |
| 480 | `self.pass_mae_guardrail` | Model field | Cờ pass MAE ratio. |
| 481 | `)` | Python tuple | Kết thúc tuple flags. |
| 482 | `if any(flag is None for flag in flags):` | Hàm `any` Python mặc định | Nếu có flag chưa biết thì kết quả tổng cũng chưa biết. |
| 483 | `return None` | Python | Trả None khi thiếu dữ liệu. |
| 484 | `return all(flags)` | Hàm `all` Python mặc định | True nếu tất cả flag đều True; False nếu có flag False. |

## Tóm tắt luồng dữ liệu theo các bảng

```text
ExperimentRun
  ├─ ExperimentConfig       : cấu hình Kalman + ARX + split ratio
  ├─ ARXArtifact            : hệ số model ARX đã train
  ├─ PipelineCycle          : từng sample sau raw -> ARX -> Kalman
  └─ EvaluationSummary      : metric tổng hợp train / validation / test
```

## Các hàm/class Django được dùng nhiều nhất

| Tên | Thuộc thư viện nào | Làm gì |
|---|---|---|
| `models.Model` | Django ORM | Base class để Django hiểu class này là bảng DB. |
| `models.TextChoices` | Django ORM | Tạo enum giá trị text cho field `choices`. |
| `models.CharField` | Django ORM | Cột chuỗi ngắn, có `max_length`. |
| `models.TextField` | Django ORM | Cột text dài, thường dùng JSON string hoặc ghi chú dài. |
| `models.FloatField` | Django ORM | Cột số thực, dùng cho sensor, Kalman, metric. |
| `models.IntegerField` | Django ORM | Cột số nguyên, dùng cho count, index, bậc ARX. |
| `models.DateTimeField` | Django ORM | Cột thời gian. `auto_now_add=True` tự set khi insert. |
| `models.ForeignKey` | Django ORM | Quan hệ nhiều-1, ví dụ nhiều cycle thuộc một run. |
| `models.OneToOneField` | Django ORM | Quan hệ 1-1, ví dụ một run có một config. |
| `models.BigAutoField` | Django ORM | Primary key số lớn tự tăng. |
| `models.Index` | Django ORM | Tạo index để query nhanh hơn. |
| `models.UniqueConstraint` | Django ORM | Ràng buộc không cho trùng tổ hợp cột. |
| `models.CheckConstraint` | Django ORM | Ràng buộc giá trị hợp lệ ở tầng DB. |
| `models.Q` | Django ORM | Tạo biểu thức điều kiện cho query hoặc constraint. |
| `@property` | Python mặc định | Biến method thành thuộc tính tính động. |
| `any()` | Python mặc định | True nếu có ít nhất một phần tử True. |
| `all()` | Python mặc định | True nếu tất cả phần tử đều True. |

## Điểm cần nhớ khi đọc file này

1. `models.py` không chạy Kalman trực tiếp. Nó chỉ định nghĩa chỗ lưu dữ liệu.
2. Dữ liệu raw nằm trong `PipelineCycle.raw_*`.
3. Dữ liệu ARX predicted nằm trong `PipelineCycle.arx_predicted`.
4. Dữ liệu sau Kalman nằm trong `PipelineCycle.kf_x_posterior`.
5. Các thông số nội bộ Kalman như R, K, innovation, P nằm trong các cột `kf_*`.
6. Metric train / validation / test nằm trong `EvaluationSummary`.
7. Các class `TextChoices` giúp tránh lưu status lung tung vào DB.
8. Các `CheckConstraint` ở `PipelineCycle.Meta` là lớp chặn cuối cùng ở database.
9. `ExperimentRun` là bảng cha, nên gần như mọi thứ đều có `run_id`.
10. Nếu muốn hiểu "một sample đi qua pipeline như nào", đọc tiếp `pipeline/store.py`, `kalman/cycle.py`, và `evaluation/metrics.py`.
