**Mô hình dự đoán hồi quy:**

Dữ liệu sẽ được lưu dưới dạng 1 bảng số, ứng với mỗi bảng ta sẽ dùng các dữ liệu theo thời gian thực để có thể train mô hình ( xem ví dụ dưới ảnh ): ![A graph showing the value of a number of different values  AI-generated content may be incorrect.](data:image/jpeg;base64...)

Và 2 mô hình LightGBM / XGBoost là mạnh nhất

**Giải thích:**

Vì đây mình sẽ lưu mỗi phút là 1 dữ liệu:

* ẩm đất hiện tại
* nhiệt độ
* độ ẩm không khí
* ánh sáng

Đây là các thông số để giúp ta nhận biết được các thuộc tính rồi tiến hành dự đoán

Đây là kiểu dữ liệu bảng chứ không phải kiểu ảnh/giọng nói.

LightGBM/XGBoost sinh ra để trị dữ liệu bảng, nên thường cho kết quả tốt

·       Ít kén dữ liệu, ít phải chỉnh

·       Không cần chuẩn hoá dữ liệu phức tạp

·       Dữ liệu thiếu vài điểm / nhiễu nhẹ vẫn chạy ổn

·       Train nhanh, dễ thử nhiều lần, phù hợp với đồ án ít các dữ liệu mẫu

Bảng so sánh các mô hình

![A screenshot of a black screen  AI-generated content may be incorrect.](data:image/png;base64...)

Linear/Ridge (tuyến tính)

·       Nó chỉ hiểu kiểu tang giảm của 1 đường thẳng

·       Nhưng greenhouse là phi tuyến: lúc đất đã khô thì khô rất nhanh, lúc đất ướt thì khô chậm, mới tưới thì tăng đột ngột nên thường thua LightGBM/XGBoost.

Random Forest: cũng tương tự lightGBM?XGBoost tuy nhiên lại hay may rủi hơn

LSTM/GRU (deep learning chuỗi thời gian)

·       cần rất nhiều dữ liệu (vài tuần–vài tháng sạch)

·       khó chỉnh tham số

·       dễ train nếu sensor nhiễu/mất dữ liệu -> đồ án mà dữ liệu ít thì thường không đáng.

Chọn LightGBM hoặc XGBoost vì:

·       mạnh nhất cho dữ liệu bảng cảm biến

·       bắt được quan hệ “nếu…thì…”

·       ít kén dữ liệu, chạy ổn cho đồ án

·       dễ giải thích

Đây bài là [bài báo cáo](https://www.mdpi.com/2624-7402/7/8/260) về hiệu xuất LSTM + XGBoost trải qua thực nghiệm nma ta dùng lisghtgbm hơn vì ta k đủ các thực nghiệm để lưu dữ liệu lớn như LSTM

**Mô hình quyết định:**

Logic ra quyết định của mô hình trong smart greenhouse hiểu đơn giản là:

Model chỉ dự đoán 1 con số (ví dụ: 60 phút nữa ẩm đất sẽ còn bao nhiêu).

Còn “ra quyết định” là luật (rule/policy) dùng con số đó + cảm biến hiện tại để bật/tắt

Ví dụ:

* Input (tại thời điểm t): ẩm đất, nhiệt độ, RH, ánh sáng + các “giá trị quá khứ”
* Output của model: 1 số dự đoán ẩm đất sau 60 phút

|  |  |
| --- | --- |
| Mô hình quyết định | Giải thích |
| Rule-based (ngưỡng + hysteresis + pulse) | Nếu đất ẩm thấp thì tưới, đủ thì tắt, phun sương theo RH/VPD |
| Fuzzy Logic Controller | Điều khiển kiểu: khô hơi nhiều → tưới nhiều tí |
| PID/PI Controller | Điều khiển liên tục để giữ 1 giá trị mục tiêu (vd RH/VPD) |
| Supervised Policy (Classifier/Regressor ra action) | Model nhìn state → xuất thẳng “tưới bao lâu” |
| Contextual Bandit | Mỗi lần chọn 1 hành động, học dần cái nào lợi nhất |
| RL (DQN/PPO/SAC…) | Agent tự học policy tối ưu qua thưởng/phạt |
| MPC (Model Predictive Control) | Dùng mô hình dự đoán để  rồi chọn hành động tốt nhất |

**Vì chúng ta đã sử dụng các mô hình dự đoán phi tuyến tính nên sẽ rất thích hợp nếu chúng ta sử dụng mô hình quyết định MPC**

**Khái niệm:** Điều khiển dự báo mô hình (MPC) là một kỹ thuật điều khiển tối ưu, trong đó các hành động điều khiển được tính toán nhằm giảm thiểu hàm chi phí cho một hệ thống động lực bị ràng buộc trên một khoảng thời gian hữu hạn, có thể thay đổi.

Ở mỗi bước thời gian, bộ điều khiển MPC nhận hoặc ước tính trạng thái hiện tại của hệ thống. Sau đó, nó tính toán chuỗi các hành động điều khiển nhằm giảm thiểu chi phí trong suốt thời gian dự báo bằng cách giải quyết bài toán tối ưu hóa có ràng buộc dựa trên mô hình nội bộ của hệ thống và phụ thuộc vào trạng thái hiện tại của hệ thống. Bộ điều khiển chỉ áp dụng cho hệ thống hành động điều khiển đầu tiên được tính toán, bỏ qua các hành động tiếp theo. Quá trình này lặp lại ở bước thời gian tiếp theo.

Nói đơn giản là nó sẽ tính toán trước và xác định là 60p nữa cần làm gì để được coi là tốt nhất

*ví dụ h là 7h, nó sẽ tính toán trong khoảng 1h từ 7h - 8h, xem xem là trong 1h tiếp theo độ ẩm đạt tới ngưỡng cần cấp ẩm hay chưa, nếu cần nó sẽ bắt đầu phun sương ngay lúc 7h đấy, đến 7h1p nó lại tiên đoán tiếp 1h tiếp theo …*

![A diagram of a model  AI-generated content may be incorrect.](data:image/png;base64...)

**Ý nghĩa ký hiệu trong hình**

* k = thời điểm hiện tại (ví dụ 7:00).
* k+1, k+2… = các bước tương lai (7:01, 7:02…).
* ref(k) = “mục tiêu” m muốn hệ đạt được (setpoint), ví dụ:
  + ẩm đất mục tiêu, hoặc dải ẩm đất
  + RH/VPD mục tiêu trong nhà kính
* u(k) = tín hiệu điều khiển m tác động lên hệ, ví dụ:
  + bật tưới nhỏ giọt bao lâu
  + bật phun sương bao lâu
* y(k) = giá trị đo từ cảm biến (output đo được), ví dụ:
  + ẩm đất, T, RH, ánh sáng
* v(k) = nhiễu/đầu vào môi trường đo được (measured disturbances), ví dụ:
  + ánh sáng (m đo được), nhiệt độ ngoài (nếu có),…
* d(k) = nhiễu không đo được (unmeasured disturbances), ví dụ:
  + gió, thay đổi bất ngờ, sai số cảm biến, rò rỉ nước…

**Plant = “hệ thật” ngoài đời (nhà kính thật của m).**

Nó nhận

* :u(k) (lệnh tưới/phun)
* v(k) (nắng/nhiệt/… đo được)
* d(k) (thứ không đo được

Và nó trả ra:

* y(k) = cảm biến đo được trong nhà kính.

**Kalman Filter (ước lượng trạng thái)**

Trong thực tế, cảm biến có nhiễu và có thứ “không đo trực tiếp” (vd trạng thái nước trong vùng rễ thật sự).

Vì vậy MPC hay có bộ ước lượng trạng thái để tạo ra:

x^(k) = “trạng thái ước lượng” (estimated states)

**Prediction Model (mô hình dự đoán)**

* Đây là “mô hình mô phỏng tương lai”:
* nhận x̂(k) + kế hoạch u + nhiễu đo được v
* dự đoán tương lai: ŷ(k+1…k+P)

**Optimization (tối ưu)**

* Mục tiêu ref(k) (m muốn ẩm đất/RH như thế nào)
* Dùng Prediction Model để thử các phương án điều khiển trong tương lai
* Rồi chọn chuỗi điều khiển tốt nhất: u(k), u(k+1), … (một dãy “control moves”)

Quy trình MPC:

* Xác định mô hình hệ thống. Định nghĩa mô hình hệ thống nội bộ mà bộ điều khiển MPC sử dụng để dự báo hành vi của hệ thống trong suốt thời gian dự đoán. Thông thường, ta thu được mô hình hệ thống này bằng cách tuyến tính hóa một hệ thống phi tuyến tại một điểm vận hành nhất định và chỉ định nó là một đối tượng LTI, chẳng hạn như ss, tf, và zpk.
* Xác định loại tín hiệu. Đối với mục đích thiết kế MPC, tín hiệu của hệ thống thường được phân loại thành các loại đầu vào và đầu ra khác nhau. Thông thường, ta sử dụng setmpcsignals để chỉ định, trong đối tượng hệ thống được định nghĩa ở bước trước, liệu mỗi đầu ra của hệ thống là tín hiệu đo được hay không đo được, và liệu mỗi đầu vào của hệ thống là biến điều khiển (tức là đầu vào điều khiển) hay là nhiễu đo được hoặc không đo được.
* Tạo đối tượng MPC. Sau khi chỉ định các loại tín hiệu trong đối tượng hệ thống, ta tạo một MPC và chỉ định trong đối tượng đó các tham số bộ điều khiển như thời gian lấy mẫu, phạm vi dự đoán và điều khiển, trọng số hàm chi phí, các ràng buộc và mô hình nhiễu. Sau đây là tổng quan về các tham số quan trọng nhất mà ta cần chọn.
  + Thời gian lấy mẫu. Một dự đoán ban đầu điển hình là thiết lập thời gian lấy mẫu của bộ điều khiển sao cho 10 đến 20 mẫu bao phủ khoảng thời gian tăng của hệ thống.
  + Khoảng thời gian dự đoán. Số lượng mẫu dữ liệu trong tương lai mà bộ điều khiển cố gắng giảm thiểu chi phí. Khoảng thời gian này phải đủ dài để nắm bắt được đáp ứng thoáng qua và bao quát các động lực quan trọng của hệ thống. Khoảng thời gian dự đoán dài hơn sẽ làm tăng cả hiệu năng và yêu cầu tính toán. Khoảng thời gian dự đoán điển hình là từ 10 đến 20 mẫu.
  + Tầm điều khiển. Số bước điều khiển tự do mà bộ điều khiển sử dụng để giảm thiểu chi phí trong suốt tầm dự đoán. Tương tự như tầm dự đoán, tầm điều khiển dài hơn sẽ làm tăng cả hiệu năng và yêu cầu tính toán. Một quy tắc chung cho tầm điều khiển là đặt nó từ 10% đến 20% của tầm dự đoán, đồng thời có tối thiểu từ hai đến ba bước.
  + Giá trị danh nghĩa. Nếu hệ thống của ta được xây dựng dựa trên việc tuyến tính hóa một mô hình phi tuyến xung quanh một điểm vận hành, thì cách tốt nhất là thiết lập các giá trị danh nghĩa cho đầu vào, trạng thái, đạo hàm trạng thái (nếu khác 0) và đầu ra. Làm như vậy cho phép ta xác định các ràng buộc đối với đầu vào và đầu ra thực tế (thay vì xác định các ràng buộc đối với độ lệch so với giá trị danh nghĩa của chúng), và cho phép ta mô phỏng vòng kín và trực quan hóa các tín hiệu dễ dàng hơn.
  + Hệ số tỷ lệ. Thực hành tốt là chỉ định hệ số tỷ lệ cho từng đầu vào và đầu ra của hệ thống, đặc biệt khi phạm vi và độ lớn của chúng rất khác nhau. Các hệ số tỷ lệ thích hợp cải thiện điều kiện số học của bài toán tối ưu hóa cơ bản và giúp việc điều chỉnh trọng số dễ dàng hơn. Một khuyến nghị tốt là đặt hệ số tỷ lệ xấp xỉ bằng khoảng biến thiên (sự khác biệt giữa giá trị tối đa và tối thiểu tính bằng đơn vị kỹ thuật) của tín hiệu liên quan.
  + Ràng buộc. Các ràng buộc thường phản ánh các giới hạn vật lý. Bạn có thể chỉ định các ràng buộc là cứng (không thể vi phạm trong quá trình tối ưu hóa) hoặc mềm (có thể vi phạm ở mức độ nhỏ). Một lời khuyên tốt là nên đặt các ràng buộc cứng, nếu cần, cho các đầu vào hoặc tốc độ thay đổi của chúng, trong khi đặt các ràng buộc đầu ra, nếu cần, là mềm. Việc đặt các ràng buộc cứng cho cả đầu vào và đầu ra có thể dẫn đến tình trạng không khả thi và nói chung là không được khuyến khích.
  + Trọng số. Ta có thể ưu tiên các mục tiêu hiệu suất của bộ điều khiển bằng cách điều chỉnh trọng số điều chỉnh hàm chi phí. Thông thường, trọng số đầu ra lớn hơn sẽ cung cấp hiệu suất theo dõi tham chiếu mạnh mẽ hơn, trong khi trọng số lớn hơn trên tốc độ biến điều khiển sẽ thúc đẩy các chuyển động điều khiển mượt mà hơn, cải thiện độ ổn định.
  + Mô hình nhiễu và tạp âm.  Mô hình dự đoán nội bộ mà bộ điều khiển sử dụng để tính toán hành động điều khiển thường bao gồm mô hình hệ thống được bổ sung thêm các mô hình nhiễu và tạp âm đo lường ảnh hưởng đến hệ thống. Mô hình nhiễu xác định các đặc tính động của các nhiễu không đo được trên đầu vào và đầu ra, tương ứng, để chúng có thể được loại bỏ tốt hơn. Theo mặc định, các mô hình nhiễu này được giả định là các mô hình tích phân (do đó cho phép bộ điều khiển loại bỏ các nhiễu dạng bậc thang) trừ khi ta chỉ định khác. Tạp âm đo lường thường được giả định là tạp âm trắng.
* Mô phỏng vòng kín. Sau khi tạo bộ điều khiển MPC, ta thường đánh giá hiệu suất của bộ điều khiển bằng cách mô phỏng nó trong vòng kín với hệ thống của mình.
* Tinh chỉnh thiết kế — Sau khi đánh giá ban đầu vòng điều khiển kín, ta thường cần tinh chỉnh thiết kế bằng cách điều chỉnh các thông số bộ điều khiển và đánh giá các kịch bản mô phỏng khác nhau. Ngoài các thông số được mô tả trong bước 3, ta có thể xem xét:
  + Sử dụng phương pháp chặn biến thao tác.
  + Đối với các hệ thống điều khiển quá mức, cần thiết lập các mục tiêu tham chiếu cho các biến được điều khiển
  + Điều chỉnh hệ số khuếch đại của bộ ước lượng trạng thái Kalman (hoặc thiết kế bộ ước lượng trạng thái tùy chỉnh)
  + Xác định các ràng buộc cuối cùng
  + Xác định các ràng buộc tùy chỉnh
  + Xác định trọng số hàm chi phí ngoài đường chéo.
* Tăng tốc quá trình thực thi
* Triển khai bộ điều khiển

**Điều khiển các hệ thống phi tuyến tính và thay đổi theo thời gian**

Thông thường, hệ thống cần điều khiển chỉ có thể được mô phỏng chính xác bằng một mô hình tuyến tính cục bộ, xung quanh một điểm vận hành nhất định. Tuy nhiên, sự mô phỏng này có thể không còn chính xác khi thời gian trôi qua và điểm vận hành của hệ thống thay đổi.

* MPC thích ứng. Nếu thứ tự (và số lượng độ trễ thời gian) của hệ thống không thay đổi, ta có thể thiết kế một bộ điều khiển MPC duy nhất (ví dụ: cho điểm vận hành ban đầu), và sau đó trong quá trình vận hành, ta có thể cập nhật mô hình dự đoán của bộ điều khiển ở mỗi bước thời gian (trong khi bộ điều khiển vẫn giả định rằng mô hình dự đoán không đổi trong tương lai, trên toàn bộ phạm vi dự đoán của nó).
* Điều khiển dự báo mô hình tuyến tính thay đổi theo thời gian (Linear Time Varying MPC) — Phương pháp này là một dạng MPC thích nghi, trong đó bộ điều khiển biết trước cách mô hình hệ thống bên trong của nó thay đổi trong tương lai, và do đó sử dụng thông tin này khi tính toán điều khiển tối ưu trên toàn bộ phạm vi dự báo. Ở đây, tại mỗi bước thời gian, ta cung cấp cho bộ điều khiển không chỉ mô hình hệ thống hiện tại mà còn cả các mô hình hệ thống cho tất cả các bước trong tương lai, trên toàn bộ phạm vi dự báo. Để tính toán các mô hình hệ thống cho các bước trong tương lai, ta có thể sử dụng các biến điều khiển và trạng thái hệ thống được bộ điều khiển MPC dự đoán ở mỗi bước làm các điểm hoạt động mà xung quanh đó một mô hình hệ thống phi tuyến có thể được tuyến tính hóa.
* MPC điều chỉnh theo mức tăng (Gain-Scheduled MPC) — Trong phương pháp này, ta thiết kế nhiều bộ điều khiển MPC ngoại tuyến, mỗi bộ cho một điểm vận hành liên quan. Sau đó, trực tuyến, ta chuyển đổi bộ điều khiển đang hoạt động khi điểm vận hành của hệ thống thay đổi. Mặc dù việc chuyển đổi bộ điều khiển khá đơn giản về mặt tính toán, phương pháp này yêu cầu nhiều bộ nhớ trực tuyến hơn (và nói chung là nhiều nỗ lực thiết kế hơn) so với MPC thích ứng. Nó nên được dành cho các trường hợp mà mô hình hệ thống tuyến tính hóa có bậc hoặc độ trễ thời gian khác nhau (và biến chuyển đổi thay đổi chậm so với động lực học của hệ thống).
* MPC phi tuyến. Ta có thể sử dụng chiến lược này để điều khiển các hệ thống có tính phi tuyến cao khi tất cả các phương pháp trước đó đều không phù hợp, hoặc khi ta cần sử dụng các ràng buộc phi tuyến hoặc các hàm chi phí không phải bậc hai. Phương pháp này đòi hỏi nhiều tính toán hơn các phương pháp trước đó, và nó cũng yêu cầu ta thiết kế và triển khai một bộ ước lượng trạng thái phi tuyến nếu trạng thái của hệ thống không hoàn toàn có sẵn. Có hai phương pháp MPC phi tuyến.
  + MPC phi tuyến đa giai đoạn.  Đối với bộ điều khiển MPC đa giai đoạn, mỗi bước tiếp theo trong tầm nhìn (giai đoạn) đều có các biến quyết định và tham số riêng, cũng như chi phí và ràng buộc phi tuyến riêng. Điều quan trọng là, các hàm chi phí và ràng buộc ở một giai đoạn cụ thể chỉ là hàm của các biến quyết định và tham số ở giai đoạn đó. Mặc dù việc chỉ định nhiều hàm chi phí và ràng buộc có thể yêu cầu nhiều thời gian thiết kế hơn, nhưng nó cũng cho phép xây dựng hiệu quả bài toán tối ưu hóa cơ bản và cấu trúc dữ liệu nhỏ hơn, giúp giảm đáng kể thời gian tính toán so với MPC phi tuyến thông thường. Hãy sử dụng phương pháp này nếu bài toán MPC phi tuyến của ta có các hàm chi phí và ràng buộc không liên quan đến các thuật ngữ xuyên giai đoạn, như thường thấy.
  + MPC phi tuyến tổng quát. Phương pháp này là dạng MPC tổng quát nhất và tốn kém nhất về mặt tính toán. Vì nó cung cấp rõ ràng các trọng số chuẩn và thiết lập giới hạn tuyến tính, nên nó có thể là điểm khởi đầu tốt cho một thiết kế mà tính phi tuyến duy nhất đến từ mô hình hệ thống.

**Filter Kalman  để ước lượng các trạng thái khác nhau của cây trồng để có các control move hợp lý**

**Mức 1 ( basic )**

Thay Kalman bằng các filter đơn giản:

**Moving Average (trung bình trượt)** lấy trung bình 5–15 phút gần nhất để giảm nhiễu.

**EMA (Exponential Moving Average)**

* mượt hơn, phản ứng nhanh hơn MA.
* công thức:

![](data:image/png;base64...)x^t​=αxt​+(1−α)x^t−1​

              (α khoảng 0.1–0.3 tuỳ mượt/nhanh)

**Median filter (lọc “spike”)** lấy median của 3–5 mẫu gần nhất để loại giá trị nhảy đột ngột

**Mức 2 ( medium) Kalman Filter 1D cho từng cảm biến**

Kalman filter dùng khi

* Ẩm đất: giảm nhiễu, ước lượng trend
* RH, nhiệt độ: mượt, chống nhiễu

**Kalman 1D** rất đơn giản: coi “giá trị thật” thay đổi chậm, đo đạc có noise.

**Mức 3 (E)KF – Extended Kalman Filter**

* Chỉ thực sự cần khi có **mô hình vật lý trạng thái** (state-space) kiểu:

![](data:image/png;base64...)xk+1​=f(xk​,uk​)+wk​,yk​=h(xk​)+vk​

và hệ phi tuyến.

**Hàm chi phí (cost function) dùng trong MPC**

Một dạng hàm chi phí đơn giản, dễ triển khai cho nhà kính thông minh (tưới nhỏ giọt + phun sương) là:

J = w1·max(0, θ\_low − θ̂)^2 + w2·max(0, θ̂ − θ\_high)^2 + w3·max(0, RĤ − RH\_max)^2 + λd·drip\_sec + λm·mist\_sec

·        θ (theta mũ): độ ẩm đất dự đoán sau 60 phút (hoặc giá trị dự đoán trên cả đường cong 60 phút).

·        RĤ (RH mũ): độ ẩm không khí dự đoán sau 60 phút.

·        θ\_low và θ\_high: ngưỡng thấp/cao của độ ẩm đất (giữ đất trong vùng an toàn).

·        RH\_max: ngưỡng tối đa của độ ẩm không khí (tránh quá ẩm gây đọng nước, tăng nguy cơ bệnh).

·        w1, w2, w3: trọng số (thường đặt w1 lớn nhất vì “để khô” nguy hiểm hơn).

·        λd, λm: hệ số phạt mức tiêu thụ (tưới/phun càng nhiều thì J càng lớn).

·        drip\_sec, mist\_sec: thời gian bật tưới nhỏ giọt / phun sương (tính theo giây) ứng với hành động đang xét.

**Giải thích trực quan “phạt khô” và “phạt úng”**

4.1. Phạt khô (dry penalty):

P\_khô = max(0, θ\_low − θ̂)^2

• Nếu θ̂ ≥ θ\_low: dự đoán vẫn nằm trên ngưỡng thấp → max(0, …) = 0 → không bị phạt.
 • Nếu θ̂ < θ\_low: dự đoán sẽ xuống dưới ngưỡng thấp (đất sắp khô) → bị phạt. Bình phương giúp “khô càng nhiều thì phạt càng nặng”.

4.2. Phạt úng (wet penalty):

P\_úng = max(0, θ̂ − θ\_high)^2

• Nếu θ̂ ≤ θ\_high: dự đoán không vượt ngưỡng cao → không bị phạt.
 • Nếu θ̂ > θ\_high: dự đoán vượt ngưỡng cao (quá ẩm/úng) → bị phạt. Bình phương giúp “quá ẩm càng nhiều thì phạt càng nặng”.

**Ràng buộc an toàn**

·        Nếu θ\_t < θ\_emergency (quá khô nguy hiểm) → tưới ngay theo chế độ an toàn (bỏ qua MPC).

·        Giới hạn tối đa tổng thời gian tưới mỗi giờ/ngày để tránh lỗi gây tưới liên tục.

·        Phun sương không chạy khi RH đã cao (ví dụ RH ≥ RH\_max) và thường hạn chế phun sương ban đêm (light thấp).

·        Nếu cảm biến lỗi/mất dữ liệu → chuyển sang chế độ điều khiển an toàn (rule-based) thay vì dùng MPC.

![A black screen with white text  AI-generated content may be incorrect.](data:image/png;base64...)

**1. Mô hình dự báo (The Model)**

* **MPC thường (LTI MPC):** Sử dụng một mô hình toán học **cố định**. Ví dụ: Bạn thiết lập rằng "Cứ tưới 1 lít nước thì độ ẩm tăng 5%". Con số này sẽ không bao giờ thay đổi dù trời nắng hay mưa.
* **Adaptive MPC:** Mô hình này **thay đổi theo thời gian**. Hệ thống hiểu rằng: "Bình thường tưới 1 lít tăng 5%, nhưng hôm nay trời nóng quá, tưới 1 lít chỉ tăng được 3% do bay hơi". Nó sẽ tự động cập nhật lại con số này vào bộ tính toán.

**2. Khả năng đối phó với sự thay đổi (Robustness)**

* **MPC thường:** Nếu môi trường thực tế khác xa với mô hình bạn nạp vào máy (ví dụ: đất bị nén chặt hơn, cảm biến bị cũ đi), kết quả điều khiển sẽ bị sai lệch (tưới quá nhiều hoặc quá ít).
* **Adaptive MPC:** Có khả năng "tự học". Tại mỗi bước thời gian, nó so sánh: **Dự đoán của nó** vs **Thực tế cảm biến trả về**. Khoảng chênh lệch (sai số) sẽ được dùng để hiệu chỉnh lại các tham số mô hình ngay lập tức.

**Chọn MPC thích ứng**

**1. Các khối thành phần chính**

**Khối Optimization (Tối ưu hóa)**

Đây là “cơ quan đầu não” của MPC.

·       Nhiệm vụ: Giải bài toán tối ưu dựa trên Hàm chi phí (Cost Function) để chọn ra chuỗi hành động tốt nhất.

·      Cách hoạt động: Nó nhìn vào mục tiêu () và các dự báo tương lai để thử nghiệm nhiều phương án điều khiển khác nhau (). Kết quả cuối cùng là chọn ra một dãy các “control moves” sao cho sai số và chi phí tài nguyên là thấp nhất.

**Khối Prediction Model (Mô hình dự đoán)**

Đây chính là nơi bạn sử dụng LightGBM/XGBoost hoặc mô hình toán học.

·       Nhiệm vụ: Đóng vai trò là một “nhà kính ảo” bên trong bộ điều khiển.

·      Cách hoạt động: Nó nhận trạng thái hiện tại () và các nhiễu môi trường () để mô phỏng xem nếu ta thực hiện lệnh thì độ ẩm đất sẽ thay đổi thế nào trong 10-20 bước tiếp theo.

**Khối State Estimation (Ước lượng trạng thái - Kalman Filter)**

Cảm biến ngoài đời thực thường bị nhiễu hoặc không đo được trực tiếp mọi thứ.

·       Nhiệm vụ: Làm sạch dữ liệu và ước lượng các trạng thái “ẩn” của cây trồng.

·       [cite\_start]Cách hoạt động: Nó sử dụng thuật toán Kalman Filter để trộn dữ liệu đo được thực tế () với dự đoán từ mô hình để tạo ra một con số tin cậy nhất ().

**Khối Plant (Đối tượng điều khiển)**

Đây chính là nhà kính thật của bạn với đầy đủ các yếu tố vật lý.

·      Nó chịu tác động của lệnh điều khiển ( - bật bơm), nhiễu đo được ( - ánh sáng mặt trời) và cả những nhiễu không đo được ( - gió, rò rỉ nước).

**2. Giải thích các ký hiệu quan trọng (Tín hiệu luân chuyển)**

**·      (**Reference): Mục tiêu bạn muốn đạt được (ví dụ: giữ độ ẩm đất ở mức 70%).

·      (Control moves): Lệnh điều khiển thực tế, ví dụ: thời gian bật bơm hoặc phun sương tính bằng giây[cite: 570, 697].

·      (Measured outputs): Dữ liệu thực tế trả về từ cảm biến nhiệt độ, độ ẩm, ánh sáng.

·      (Measured disturbances): Các yếu tố môi trường ta đo được nhưng không điều khiển được (như nắng lên cao).

·      (Unmeasured disturbances): Những biến số “phá hoại” không lường trước được (như sai số cảm biến hay thay đổi thời tiết bất ngờ)[cite: 578, 580].

**3. Đánh giá về độ hợp lý**

Mô hình này rất hợp lý vì nó giải quyết được tính “nhìn xa trông rộng”. Thay vì đợi đất khô mới tưới (như Rule-based), sơ đồ này cho phép hệ thống tính toán: “Nếu bây giờ không tưới, thì 60 phút nữa cây sẽ bị héo do nắng gắt ()”, từ đó ra quyết định tưới ngay lập tức một lượng vừa đủ.

Một lưu ý nhỏ cho bạn: Trong ảnh có đề cập đến việc tuyến tính hóa (linearization) hệ phi tuyến. Nếu bạn dùng Adaptive MPC như chúng ta đã thảo luận, khối Prediction Model sẽ được cập nhật liên tục các tham số này ở mỗi bước thời gian để bám sát thực tế hơn.

**Đầu tiên là về state Kalma filter**

Công thức tổng quát

là phương trình trạng thái tổng quát (state transition) của Kalman filter trong dạng rời rạc. Nó mô tả “trạng thái thật” được sinh ra từ trạng thái trước đó + tác động điều khiển + nhiễu quá trình.

Kalman filter không biết thật, nên nó tạo ước lượng dự đoán (prior) bằng cách bỏ phần nhiễu (vì là ngẫu nhiên, kỳ vọng bằng 0):

là bước Predict (dự đoán**)** của Kalman filter: *dự đoán trạng thái tại thời điểm trước khi dùng số đo mới .*

**Ý nghĩa ký hiệu:**

* : ước lượng tại thời điểm k, *dựa trên dữ liệu đến thời điểm k−1* → gọi là prior / predicted state.
* : ước lượng “đã hiệu chỉnh” ở bước trước (sau khi đã dùng đo ) → gọi là posterior.
* : ma trận (hoặc hệ số) mô tả hệ tự tiến hóa từ sang (state transition).
* : ma trận/hệ số cho biết tác động của điều khiển lên trạng thái.
* : tín hiệu điều khiển tại bước đó (ví dụ thời lượng tưới, mức bơm).

**Giải thích công thức**

Nó nói: “Trạng thái dự đoán ở bước ” =

1. **Trạng thái tốt nhất ở bước** ,
2. **được đưa sang bước**  theo động học ,
3. **cộng thêm ảnh hưởng của điều khiển** .

Kalman làm vậy vì phần nhiễu quá trình là ngẫu nhiên (kỳ vọng 0), nên dự đoán dùng phần “deterministic” của mô hình.

Công thức 1D

là **Kalman gain** (hệ số khuếch đại/ trọng số Kalman). Nó quyết định **tin cảm biến bao nhiêu** so với **tin dự đoán bao nhiêu** trong bước update:

Kz là đại lượng đo cảm biến

là đại lượng ước lượng chưa dùng số đo mới cho thời điểm hiện tại

**Bước 1 — Predict covariance**

**Bước 2 — Kalman gain**

**Bước 3 — Update estimate**

**Bước 4 — Update covariance**

là **sai số hiệp phương sai của ước lượng** (estimate error covariance).

Trong 1D (lọc 1 cảm biến), nó chỉ là **một số**:

* : giá trị “thật” (không biết)
* : giá trị bạn ước lượng sau khi đã cập nhật bằng đo

biểu thị dự đoán trước độ không chắc

: phương sai nhiễu quá trình (model/process noise).

* Nếu hệ thay đổi khó lường (bay hơi, nắng) → **Q lớn** → lớn → lớn → bám đo nhanh hơn.

**1) Predict (dự đoán)**

Dự đoán trạng thái và độ không chắc chắn ở thời điểm *trước khi* nhìn đo mới.

**Công thức tổng quát**

* thường **tăng** so với vì qua thời gian bạn thêm bất định (nhiễu quá trình).

**2) Gain (Kalman Gain )**

Tính để quyết định “tin đo hay tin dự đoán”.

**Công thức tổng quát**

Nguồn: Wikipedia Kalman filter.

Nếu 1D và đo trực tiếp (H = 1)

* lớn (sensor nhiễu) → nhỏ → tin dự đoán.
* lớn (mô hình không chắc) → lớn → tin cảm biến.

**3) Update covariance (cập nhật )**

Sau khi đã dùng đo mới, bạn cập nhật lại độ không chắc của ước lượng: **giảm**.

**Công thức tổng quát**

Nguồn: Wikipedia Kalman filter.

**Nếu 1D và**

**Trực giác**

* Nếu lớn (tin đo nhiều) → giảm mạnh.
* Nếu nhỏ (tin dự đoán) → giảm ít.

lọc 1 cảm biến và chọn :

* **Predict:**
* **Gain:**
* **Update:**

**Chi phí**

**Cost kiểu Setpoint / Tracking**

**Công thức**

**Ý nghĩa tổng thể**

* **Hạng 1**: phạt sai lệch giữa “giá trị muốn đạt” và “giá trị dự đoán/đạt được” → bám setpoint.
* **Hạng 2**: phạt việc điều khiển thay đổi quá mạnh → điều khiển mượt, ít bật/tắt liên tục, giảm hao mòn bơm/van.

**Giải thích từng ký hiệu**

* : tổng chi phí (cost) mà MPC muốn **minimize**.
* : chỉ số bước trong tương lai trên chân trời dự đoán.
* : *prediction horizon* (số bước tương lai mà bạn quan tâm đến lỗi bám mục tiêu).
  + Ví dụ phút, muốn nhìn 60 phút → .
* : *control horizon* (số bước tương lai mà bạn cho phép tối ưu điều khiển tự do).
  + Thường . Sau bước , hay giả sử giữ không đổi hoặc theo quy tắc đơn giản.
* : giá trị **đầu ra/trạng thái** ở bước trong tương lai (thường là **giá trị dự đoán**).
  + Ví dụ: độ ẩm đất dự đoán ở : .
* : *reference* (setpoint/trajectory) tại bước .
  + Ví dụ: muốn giữ ở 70% → (có thể là hằng hoặc thay đổi theo thời gian).
* : lệnh điều khiển (control input) tại bước .
  + Ví dụ: thời lượng tưới ở mỗi chu kỳ (giây) hoặc mức công suất.
* : độ thay đổi điều khiển:

* Phạt để tránh “giật” điều khiển (bật/tắt liên tục).
* : trọng số phạt lỗi bám setpoint ở bước .
  + Lớn → ưu tiên bám mục tiêu mạnh.
* : trọng số phạt độ “giật” điều khiển ở bước .
  + Lớn → điều khiển mượt hơn, nhưng có thể phản ứng chậm hơn.

Vì sao có bình phương ?

·       Luôn không âm, phạt lỗi lớn mạnh hơn lỗi nhỏ, và tiện cho tối ưu (đặc biệt Linear MPC/QP).

**B) Cost kiểu Range / Zone**

**Công thức**

**Ý nghĩa tổng thể**

* Bạn **không cần bám đúng 70%**; bạn chỉ cần **độ ẩm nằm trong vùng an toàn** .
* Nếu dự đoán vẫn nằm trong vùng → **không bị phạt lỗi** (cost = 0 cho phần đó).
* Chỉ khi vượt ra khỏi vùng (quá khô hoặc quá ẩm) → mới bị phạt, thường phạt mạnh (bình phương).

**Giải thích từng ký hiệu**

* : tổng chi phí cần minimize.
* : prediction horizon (số bước dự đoán tương lai dùng để tính phạt vùng).
* : control horizon (số bước tối ưu điều khiển).
* : biến bạn đang điều khiển/quan tâm (ví dụ **độ ẩm đất**).
* : ngưỡng dưới (quá khô).
* : ngưỡng trên (quá ẩm/úng).
* : **độ ẩm dự đoán tại thời điểm**  dựa trên thông tin có ở thời điểm .
  + Ký hiệu “” nghĩa là: *dự đoán từ thời điểm hiện tại*.
* : chỉ dương khi **dự đoán thấp hơn ngưỡng** (quá khô).
  + Nếu → biểu thức = 0 → không phạt.
* : chỉ dương khi **dự đoán vượt ngưỡng trên** (quá ẩm).
* : trọng số phạt cho vi phạm dưới/vi phạm trên.
  + lớn → “rất sợ khô” (ưu tiên tránh khô hơn).
  + lớn → “rất sợ úng” (ưu tiên tránh úng hơn).
* : điều khiển tại bước (ví dụ **giây tưới/phun** trong chu kỳ đó).
* : trọng số phạt tài nguyên/tiêu thụ (nước/điện/hao bơm).
  + lớn → hạn chế tưới/phun nhiều.
* : tổng “chi phí tài nguyên” trên control horizon.
  + Có thể thay bằng nếu muốn phạt mạnh hành động lớn.

Vì sao zone/range hay dùng trong nhà kính?

 Vì cây thường “ổn” trong một khoảng, không nhất thiết bám đúng 1 giá trị → tiết kiệm nước và tránh bật/tắt liên tục.

Tại thời điểm , MPC “nhìn” tới (60 phút) và tính một số cho mỗi phương án điều khiển ứng viên

Vì tại thời điểm , bạn không biết nên tưới 0s, 5s hay 10s.
 MPC sẽ tạo nhiều chuỗi hành động ứng viên (candidates) trên horizon, ví dụ:

* Chuỗi A:
* Chuỗi B:
* Chuỗi C:

Mỗi chuỗi là một “kế hoạch tưới 60 phút tới”.

Với mỗi chuỗi, bạn dùng mô hình dự đoán để tạo ra một chuỗi dự đoán độ ẩm:

rồi tính ra một số .

→ Do có nhiều chuỗi ứng viên nên sẽ có nhiều giá trị :

**Cách tính “một lần” cho một chuỗi ứng viên**

Ví dụ bạn dùng zone/range (khô quá thì phạt) + phạt nước:

* Phần là “phạt vi phạm trong 60 phút tới”
* Phần là “tốn nước”

Mỗi chuỗi khác nhau → dự đoán khác nhau → khác nhau.

**Nó so sánh với cái gì để biết nhỏ nhất?**

Nó so sánh các của các chuỗi ứng viên với nhau.

Cụ thể:

* Tính cho chuỗi A
* Tính cho chuỗi B
* Tính cho chuỗi C
* …

Sau đó chọn:

và lấy chuỗi tương ứng .

Đây chính là “optimization” (tối ưu). Với enumeration thì tối ưu chỉ là quét và lấy min.

Sau khi chọn được chuỗi tốt nhất , MPC không thực hiện cả chuỗi.

Nó chỉ thực hiện phần tử đầu tiên:

Ví dụ nếu chuỗi tốt nhất là thì tại phút này bạn tưới 10s.

Sau phút, sang thời điểm :

* bạn đo lại cảm biến (có thể khác dự đoán vì nắng, gió…),
* rồi chạy lại toàn bộ quá trình và chọn chuỗi mới.

Giả sử:

* hiện tại
* nếu không tưới thì mỗi bước 5 phút giảm 1% (để minh hoạ)
* nếu tưới 10s ở bước đầu thì tăng +4% ngay bước kế

Chuỗi A:
 → sau 1–2 bước sẽ xuống <60% → bị phạt nhiều → lớn

Chuỗi B:
 → tăng lên 65% rồi giảm dần, trong 60 phút vẫn >=60% → phạt gần 0, chỉ tốn nước → nhỏ

**Chuỗi C:
 → cũng không khô nhưng tốn nước hơn B → >**

**Kết quả: chọn chuỗi B vì nhỏ nhất.**

**1) Các phương pháp ra quyết định tưới**

**A. Theo cân bằng nước & ET (ET-based scheduling)**

* Ý tưởng: cây mất nước theo bốc thoát hơi → mình bù lại theo ETc.
* Chuẩn kinh điển: FAO-56 (Penman–Monteith) để tính ET₀ rồi suy ra ETc = Kc·ET₀.

Công thức:

* ETc:
* ET₀ (FAO Penman–Monteith) (dạng chuẩn FAO-56):

(Các ký hiệu đúng theo FAO-56)

Lượng tưới theo ET (quy đổi ra thời gian bơm/van):

* Nhu cầu nước theo “độ sâu” (mm) trong ngày/chu kỳ:
* Quy đổi ra thể tích:
* Quy đổi ra thời gian chạy (drip):

Trong đó là tổng lưu lượng toàn hệ (m³/s hoặc m³/h).

FAO-56 cũng cung cấp nền tảng “tưới đúng lúc/đúng lượng” theo cân bằng nước vùng rễ.

**B. Theo ngưỡng ẩm đất (Sensor threshold / on-demand)**

* Ý tưởng: đặt ngưỡng thấp (bắt đầu tưới) và ngưỡng cao (dừng tưới) để tránh bật/tắt liên tục (hysteresis).
* Đây là logic cực phổ biến cho soil moisture sensor controller.

Luật đơn giản (hysteresis):

* Nếu → tưới
* Nếu → dừng
* Nếu nằm giữa → giữ trạng thái trước

Cách này cực hợp để nhét vào MPC bằng ràng buộc/penalty (m đang làm), hoặc dùng làm “fallback rule”.

**C. Theo FAO-56: TAW/RAW (ngưỡng sinh lý vùng rễ)**

Đây là cách “đặt ” có cơ sở nông học thay vì chọn bừa.

* TAW (Total Available Water):
* RAW (Readily Available Water):
* Tiêu chí tưới để tránh stress: tưới trước khi độ thiếu hụt vùng rễ vượt RAW (FAO-56 viết dạng điều kiện tránh stress).

Nối sang ngưỡng :

* Khi chạm thì tương ứng chính là “điểm bắt đầu tưới” hợp lý theo cây.

**2) Mô hình khi nào tưới / dừng bằng cân bằng nước vùng rễ**

FAO-56 mô tả cân bằng nước vùng rễ bằng biến “độ thiếu hụt” (root zone depletion) và khuyến nghị tưới trước khi hết RAW.

**Dạng tổng quát (ý nghĩa vật lý):**

* **: tưới, : mưa hữu hiệu, : bốc thoát hơi cây, : thấm sâu, : chảy tràn.**

**Từ góc nhìn điều khiển:**

* **“Khi nào tưới” = khi dự báo hoặc tiến tới vùng stress (RAW) trong horizon MPC.**
* **“Dừng khi nào” = khi đạt / đạt lượng bù / hoặc thấy VPD & nhiệt độ đang khiến ET tăng mạnh nên chia nhỏ chu kỳ (pulse).**

**3) Quy đổi “lượng tưới” thành “giây tưới” cho tưới nhỏ giọt (drip)**

Nếu hệ m là drip, m cần thêm lớp “thuỷ lực”:

**A. Lưu lượng đầu nhỏ giọt theo áp**

FAO nêu quan hệ điển hình:

(với là lưu lượng emitter, là áp, là hằng số emitter).

**B. Tổng lưu lượng & thời gian chạy**

* (N emitters đang mở)
* Nếu cần thể tích :

FAO cũng có ví dụ “duration of application” trong thiết kế drip (để m cite khi viết phần triển khai).

**4) Khi nào thổi quạt / phun sương: dùng RH, nhiệt độ, VPD và “chống đọng sương”**

Trong nhà kính, điều khiển quạt/phun sương nên dựa trên (T, RH) nhưng cách “đúng bài” là chuyển sang VPD vì VPD liên quan trực tiếp tới thoát hơi và stress.

**A. Công thức VPD (chuẩn dùng rộng rãi)**

* Áp suất hơi bão hoà:
* Áp suất hơi thực:
* VPD:

**B. Luật điều khiển quạt (ventilation) theo bệnh & ngưng tụ**

* **Tài liệu quản lý nhiệt nhà kính khuyến cáo tránh RH cao (ví dụ >80–85%) vì tăng nguy cơ bệnh và giảm thoát hơi, và gợi ý thông gió/“heat-and-vent” để giảm ẩm, tránh ngưng tụ.**

**Logic gợi ý (đủ để viết thành luật / đưa vào MPC constraint):**

* Bật quạt/thoáng khí khi:
  + hoặc
  + (ví dụ vùng 80–85% tuỳ cây/giai đoạn)
  + hoặc nguy cơ đọng sương (xấp xỉ theo “dew point gap”):

              (nếu chênh nhỏ → dễ ngưng tụ trên lá/khung)

Điểm hay của dew point: nó là biến “độ ẩm tuyệt đối” thuận tiện để suy luận ngưng tụ; NIST có thảo luận dew point như đại lượng biểu diễn độ ẩm trong tính toán.

**C. Luật phun sương/mist (nếu có)**

* Mist/fog làm giảm nhiệt nhưng tăng RH ⇒ nên ràng buộc bởi VPD & RH\_max.
* “Luật thực dụng”:
  + Nếu cao và quá cao (không khí quá khô) → mist ngắn xung (pulse) để kéo VPD về vùng mục tiêu.
  + Nếu gần hoặc nguy cơ ngưng tụ → không mist, ưu tiên quạt/thoáng.

**1) Tóm tắt từng đề mục lớn của trang này**

**Chapter 1 – Introduction to evapotranspiration**

Giải thích nền tảng về **bay hơi (evaporation)**, **thoát hơi nước của cây (transpiration)**, và **ET = evapotranspiration** là tổng của hai quá trình đó. Chương này cũng phân biệt **ET₀** (chuẩn tham chiếu), **ETc** (cây trồng trong điều kiện chuẩn), và **ETc adj** (điều kiện thực tế có stress/quản lý khác chuẩn), đồng thời nêu các yếu tố ảnh hưởng như bức xạ, nhiệt độ, ẩm không khí, gió, loại cây, và điều kiện quản lý. Nó còn cho đổi đơn vị rất quan trọng: **1 mm nước trên 1 ha = 10 m³/ha**.

**Chapter 2 – FAO Penman–Monteith equation**

Đây là chương xác lập **FAO Penman–Monteith** là phương pháp chuẩn để tính **ET₀** từ dữ liệu khí tượng. Chương này giải thích vì sao cần một phương pháp chuẩn duy nhất, mô tả phương trình, dữ liệu cần dùng, và bề mặt tham chiếu chuẩn.

**Chapter 3 – Meteorological data**

Nói về dữ liệu khí tượng cần để tính ET₀: **bức xạ mặt trời, nhiệt độ, ẩm không khí, tốc độ gió**, cùng các thông số khí quyển đi kèm. Chương này cũng bàn về đo đạc, ước lượng dữ liệu thiếu, và yêu cầu dữ liệu tối thiểu.

**Chapter 4 – Determination of ET₀**

Trình bày cách **tính ET₀ thực tế** theo Penman–Monteith, theo các bước tính toán, theo các bước thời gian khác nhau, và cả cách xử lý khi thiếu dữ liệu. Có thêm phương pháp pan evaporation như phương án thay thế.

**Chapter 5 – Introduction to crop evapotranspiration (ETc)**

Đây là cầu nối từ **ET₀ sang ETc**. Ý tưởng trung tâm là:

hoặc tách chi tiết hơn:

Chương này giải thích khi nào dùng hệ số cây trồng đơn , khi nào dùng dạng kép .

**Chapter 6 – ETc using single crop coefficient**

Dùng **một hệ số**  cho toàn bộ ETc. Phù hợp khi bạn muốn mô hình đơn giản hơn, ít dữ liệu hơn. Chương này nói về độ dài các giai đoạn sinh trưởng, các giá trị theo giai đoạn, và cách dựng đường cong .

**Chapter 7 – ETc using dual crop coefficient**

Tách ETc thành hai phần:

Trong đó là phần **thoát hơi qua cây**, còn là phần **bay hơi từ mặt đất**. Cách này chi tiết hơn, đặc biệt hữu ích khi có **sự kiện tưới / mưa làm ướt mặt đất**, nên phù hợp hơn cho **lập lịch tưới hằng ngày** và các bài toán điều khiển.

**Chapter 8 – ETc under soil water stress conditions**

Đây là chương quan trọng nhất cho bài của bạn. Nó đưa vào:

* **TAW**: tổng lượng nước cây có thể dùng trong vùng rễ
* **RAW**: phần nước có thể mất đi mà cây chưa stress
* **Ks**: hệ số stress nước
* **soil water balance**: phương trình cân bằng nước vùng rễ
* **forecasting/allocating irrigations**: lên lịch tưới khi nào và bao nhiêu

Công thức trung tâm của chương là:

và phương trình cân bằng nước trong vùng rễ để theo dõi độ thiếu nước theo ngày.

**Chapter 9 – ETc for natural/non-typical vegetation**

Áp dụng cho thảm thực vật không điển hình, thưa, tự nhiên, hoặc không “chuẩn nông học”. Chủ yếu là cách hiệu chỉnh các hệ số khi độ che phủ, LAI, hoặc kiểm soát khí khổng khác đi.

**Chapter 10 – ETc under various management practices**

Phân tích ảnh hưởng của **mulch, xen canh, cây viền, oasis effect, thực hành quản lý** tới ETc. Nghĩa là cùng một cây nhưng cách quản lý khác thì ETc có thể khác.

**Chapter 11 – ETc during non-growing periods**

Xử lý giai đoạn không sinh trưởng: đất trống, phủ cỏ chết, phủ cỏ sống, băng tuyết. Dùng khi mô phỏng quanh năm hoặc ngoài mùa vụ.

**Annexes**

Các phụ lục cung cấp bảng đơn vị, bảng khí tượng, nền tảng vật lý, kiểm tra dữ liệu thời tiết, và đặc biệt có **Annex 8** là một **ví dụ spreadsheet hoàn chỉnh để lập lịch tưới bằng dual Kc + soil-water balance**.

**2) Cái bạn cần nhất từ FAO: chuỗi công thức “ra quyết định tưới”**

Muốn biết **cần tưới bao nhiêu**, FAO đi theo chuỗi này:

**Bước A: Tính ET₀**

Bằng FAO Penman–Monteith từ dữ liệu thời tiết. Đây là “nhu cầu bốc thoát hơi chuẩn” của khí quyển.

**Bước B: Tính ETc**

Nếu đơn giản:

Nếu chi tiết hơn:

Trong đó dual coefficient phù hợp hơn nếu bạn quan tâm hiệu ứng mưa/tưới làm ướt bề mặt đất.

**Bước C: Nếu cây bị thiếu nước thì hiệu chỉnh stress**

hoặc dạng đơn giản hơn:

Nếu chưa stress thì . Nếu thiếu nước thì .

**Bước D: Tính “kho nước” trong vùng rễ**

FAO dùng hai đại lượng rất quan trọng:

* : tổng nước cây dùng được trong vùng rễ
* : lượng có thể cạn trước khi cây bắt đầu stress
* : độ sâu vùng rễ
* , : độ ẩm thể tích ở field capacity và wilting point.

**Bước E: Cập nhật cân bằng nước vùng rễ theo thời gian**

Phương trình gốc:

Trong đó:

* : depletion của vùng rễ ở cuối ngày/bước
* : mưa
* : runoff
* : lượng tưới đã thấm
* : capillary rise
* : nước mất do cây + bay hơi
* : thấm sâu vượt vùng rễ.

Ý nghĩa của :

* : vùng rễ no nước tới field capacity
* càng lớn: càng thiếu nước
* khi : bắt đầu có nguy cơ stress, cần tưới.

**3) Từ “cần tưới bao nhiêu mm” sang “bao nhiêu giây”**

Đây là đoạn FAO không viết trực tiếp theo kiểu “giây bật bơm”, vì FAO làm ở mức **depth of irrigation** trước. Nhưng mình nối nó ra cho bạn như sau.

**3.1. Lượng nước tưới cần thiết ở bước**

Nếu mục tiêu là **nạp lại vùng rễ về gần field capacity**, thì cách tự nhiên nhất là chọn:

vì FAO nói để tránh percolation sâu thì **net irrigation depth nên nhỏ hơn hoặc bằng depletion hiện tại**:

Trong thực tế điều khiển, bạn có thể chọn:

hoặc nếu chỉ muốn kéo về ngưỡng an toàn chứ không bơm đầy:

với là depletion mục tiêu.

**3.2. Đổi từ mm sang thể tích nước**

Từ đổi đơn vị của FAO:

* 1 mm trên 1 ha = 10 m³/ha

Suy ra theo đúng hình học:

* **1 mm nước trên 1 m² = 1 lít**

nên nếu diện tích tưới hiệu dụng là , thì:

Đây là suy luận trực tiếp từ quy đổi của FAO.

**3.3. Đổi từ thể tích sang thời gian bơm**

Nếu tổng lưu lượng cấp nước thực vào vùng tưới là , thì:

Nếu có hiệu suất hệ thống (mất mát ống, phân bố không đều, rò rỉ), thì:

Kết hợp lại:

Đây chính là công thức mà bạn đang cần cho MPC.

**4) Gắn trực tiếp vào bài toán MPC của bạn**

Trong MPC, biến điều khiển của bạn là:

Thì bạn cần một hàm đổi từ **giây tưới** sang **độ sâu nước thấm vào đất**:

Nếu tính bằng L/s, tính bằng m², thì ra luôn đơn vị mm, vì 1 L/m² = 1 mm. Công thức này là hệ quả của phần đổi đơn vị FAO kết hợp với lưu lượng bơm.

Khi đó phương trình cân bằng nước theo từng bước điều khiển trở thành:

Nếu bạn tạm bỏ mưa, runoff, capillary rise, deep percolation trong nhà kính, mô hình đơn giản là:

và vì

nên:

Đây là phương trình rất đẹp để bỏ vào MPC.

**5) Nếu bạn muốn dùng “độ ẩm đất %” thay vì depletion**

FAO gốc làm trên **water depth trong vùng rễ** vì nó vật lý hơn. Nhưng bạn có thể đổi qua độ ẩm thể tích.

Từ:

và

(theo công thức depletion từ độ ẩm đất đo được), FAO cũng dùng dạng này để khởi tạo depletion.

Suy ra:

Nghĩa là:

* MPC có thể tối ưu trên
* rồi đổi sang để so sánh với cảm biến độ ẩm đất.

Cách này thường sạch hơn việc tối ưu trực tiếp trên “% cảm biến ADC”.

**6) Còn lấy kiểu gì?**

FAO nói:

* nếu thì
* nếu thì , tính theo Eq. 84 dựa trên , , và .

Nói dễ hiểu:

* còn trong vùng an toàn: cây hút nước bình thường
* vượt quá mức cạn cho phép: cây bị stress, transpiration giảm

Trong nhà kính nhỏ, nếu mục tiêu của bạn là **không để stress xảy ra**, thì giai đoạn đầu có thể đơn giản hóa:

* luôn giữ
* khi đó cứ lấy

Như vậy mô hình sẽ gọn hơn rất nhiều.

**7) Phần liên quan trực tiếp tới “tưới bao nhiêu” trong FAO là gì?**

Phần sát nhất là:

**Chapter 8 – Forecasting or allocating irrigations**

FAO nói rõ:

* phải dùng **soil water balance**
* mục tiêu là tưới **đúng lúc và đúng lượng**
* để tránh stress thì tưới trước hoặc ngay khi RAW bị cạn
* để tránh thấm sâu thì **net irrigation depth không nên vượt root zone depletion**.

**Annex 8**

Cho một ví dụ spreadsheet hoàn chỉnh dùng:

* ETc
* soil-water balance hằng ngày
* từ đó xác định lịch tưới.

**8) Công thức hoàn chỉnh bạn có thể dùng ngay cho project**

Nếu làm bản đơn giản nhưng đúng tinh thần FAO, bạn có thể dùng bộ này:

**Mô hình nước vùng rễ**

**Lượng tưới do bơm trong bước**

**ET cây**

Bản đơn:

Bản chi tiết:

Nếu có stress:

**Ràng buộc an toàn**

**Luật trigger cổ điển**

* nếu : chưa cần tưới mạnh
* nếu : cần tưới

**Đổi ngược ra thời gian cần để bù đúng lượng thiếu**

Nếu bạn muốn kéo từ về , thì:

Đây là công thức “ra số giây” trực tiếp.

**9) Ví dụ rất cụ thể**

Giả sử:

* diện tích tưới hiệu dụng
* bơm/nhỏ giọt cấp thực tế
* hiệu suất
* depletion hiện tại
* muốn kéo về

Thì:

Thể tích cần:

Thời gian bơm:

Tức là tưới khoảng **63 giây**.

Nếu trong MPC, bạn sẽ không dùng trực tiếp công thức này để chốt luôn, mà sẽ:

* thử
* suy ra
* cập nhật
* tính
* chọn chuỗi có cost nhỏ nhất.

**10) Kết luận ngắn gọn**

Từ FAO, công thức logic chuẩn là:

Cụ thể:

Nói thẳng ra: **FAO cho bạn cách tính “cần bao nhiêu mm nước”**, còn **“bao nhiêu giây”** là bước đổi từ mm sang thể tích rồi chia cho lưu lượng bơm.

Nếu bạn muốn, lượt tiếp theo mình sẽ viết cho bạn một **mô hình state-space hoàn chỉnh cho MPC tưới**, dùng đúng ký hiệu:

* state = hoặc
* input = (giây bơm)
* disturbance = , nhiệt độ, RH
* output = độ ẩm đất cảm biến đo được.