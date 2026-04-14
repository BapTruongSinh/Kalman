# Phân Tích Chi Tiết `data_generator.py`

## 1. Mục đích của tài liệu này

Tài liệu này tập trung phân tích riêng file [`data_generator.py`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py), không chỉ mô tả file làm gì mà còn giải thích:

- vì sao generator được thiết kế như vậy
- vì sao các rule lại đặt ở các ngưỡng đó
- vì sao dữ liệu sinh ra phù hợp cho bài toán ARX(2,2,1)
- vì sao generator này tốt hơn nhiều so với việc sinh dữ liệu ngẫu nhiên đơn giản

Nói ngắn gọn, đây là tài liệu để bạn trả lời câu hỏi:

> “Vì sao bộ dữ liệu synthetic này lại đáng tin cho việc nhận dạng ARX của nhà kính mini?”

## 2. Vai trò của `data_generator.py` trong toàn dự án

File này là nền móng của cả đồ án vì nó quyết định:

- biến mục tiêu là gì
- các input nào tác động lên hệ
- động học thật của hệ có dạng ra sao
- mức khó của bài toán nhận dạng
- chất lượng dữ liệu dùng để train, validate, test

Nếu generator thiết kế kém, mọi thứ phía sau đều bị ảnh hưởng:

- mô hình có thể fit đẹp nhưng vô nghĩa
- tham số có thể không có ý nghĩa vật lý
- notebook có thể thuyết phục về mặt hình ảnh nhưng không thuyết phục về mặt học thuật

Do đó, `data_generator.py` không chỉ là file “tạo data”, mà thực chất là:

- định nghĩa vật lý giả lập của hệ
- định nghĩa logic điều khiển giả lập
- định nghĩa mức độ excitation cho bài toán system identification

## 3. Ý tưởng thiết kế tổng thể

Generator này không đi theo kiểu:

- random hết mọi thứ
- rồi sau đó fit model vào dữ liệu ngẫu nhiên

Thay vào đó, nó theo triết lý:

1. giả lập một nhà kính mini có hành vi hợp lý
2. xây động học đủ đơn giản để ARX có thể học được
3. nhưng vẫn đủ phong phú để bài toán không trở thành “quá dễ”
4. thêm cơ chế excitation có kiểm soát để đảm bảo dữ liệu giàu thông tin

Đây là một lựa chọn rất đúng cho đồ án nhận dạng hệ, vì mục tiêu của bạn không phải tạo dữ liệu thật nhất có thể, mà là tạo dữ liệu:

- có logic vật lý
- có logic điều khiển
- có khả năng nhận dạng
- có thể dùng để đánh giá mô hình một cách công bằng

## 4. Cấu trúc của file theo từng khối

Về mặt cấu trúc, file có thể chia thành 8 khối chính:

1. định nghĩa tham số thật `TRUE_PARAMS`
2. ánh xạ tháng sang mùa
3. điều chỉnh setpoint theo thời gian trong ngày
4. tạo lịch thời gian và profile theo tháng
5. tạo môi trường ngoài trời và ánh sáng
6. tạo rule cho actuator `Drip`, `Mist`, `Fan`
7. tạo động học nhiệt và ẩm trong nhà kính
8. sinh `Soil_Moisture` theo phương trình ARX thật

Mỗi khối đều có ý nghĩa riêng, và quan trọng hơn là các khối này nối với nhau khá logic.

## 5. Phân tích `TRUE_PARAMS`

Định nghĩa ở:

- [`data_generator.py#L5`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L5)

Generator dùng các tham số:

- `a1 = 0.965`
- `a2 = 0.025`
- `b_temp_1 = -0.008`
- `b_temp_2 = -0.004`
- `b_humi_1 = 0.0025`
- `b_humi_2 = 0.0012`
- `b_light_1 = -0.00022`
- `b_light_2 = -0.00010`
- `b_drip_1 = 1.25`
- `b_drip_2 = 1.85`
- `b_mist_1 = 0.05`
- `b_mist_2 = 0.03`
- `b_fan_1 = -0.05`
- `b_fan_2 = -0.03`
- `noise_sigma = 0.25`

## 5.1 Vì sao cần `a1` và `a2`

`a1` và `a2` là phần tự hồi quy của độ ẩm đất.

Ý nghĩa:

- độ ẩm đất không thay đổi tức thời
- trạng thái hiện tại phụ thuộc mạnh vào trạng thái gần trước đó
- quá trình có tính quán tính

Việc chọn:

- `a1` lớn
- `a2` nhỏ hơn nhiều

là rất hợp lý vì:

- nó tạo ra memory mạnh ở một bước gần
- nhưng vẫn có dấu vết của bước thứ hai
- giúp ARX(2,2,1) có lý do tồn tại thật sự

Nếu cả `a1` và `a2` đều nhỏ:

- độ ẩm đất sẽ phản ứng quá nhanh
- mất ý nghĩa vật lý

Nếu `a1` quá gần 1 và `a2` quá lớn:

- hệ có thể quá ì
- hoặc khó ổn định hơn

## 5.2 Vì sao `Drip` mạnh nhất

`b_drip_1` và `b_drip_2` lớn nhất trong các input.

Điều này đúng vật lý vì:

- tưới nhỏ giọt là cơ chế trực tiếp làm tăng độ ẩm đất
- nhiệt độ, ánh sáng, độ ẩm không khí chỉ tác động gián tiếp
- `Mist` chủ yếu ảnh hưởng không khí, không phải đất

Việc chọn:

- `b_drip_2 > b_drip_1`

là một quyết định rất hay, vì nó mô phỏng:

- nước không ngấm vào đất ngay toàn bộ
- có độ trễ thấm
- tác động ở bước thứ hai còn mạnh hơn bước đầu

Điều này làm bài toán ARX có chiều sâu hơn là một mô hình phản ứng tức thời.

## 5.3 Vì sao `Mist` nhỏ hơn `Drip`

`Mist` có tác động dương lên đất nhưng nhỏ:

- `b_mist_1 = 0.05`
- `b_mist_2 = 0.03`

Điều này hợp lý vì:

- sương chủ yếu làm tăng độ ẩm không khí
- có thể gián tiếp giảm thoát hơi nước
- nhưng không thể mạnh như tưới nhỏ giọt

Nếu `Mist` được đặt lớn quá:

- mô hình sẽ không còn giống nhà kính mini
- việc giải thích “Drip là actuator chính cho đất” sẽ bị phá

## 5.4 Vì sao `Fan` mang dấu âm

`Fan` có hệ số âm:

- quạt làm giảm độ ẩm không khí
- tăng thông gió
- làm đất khô nhanh hơn gián tiếp

Việc `Fan` không âm quá mạnh cũng là đúng, vì:

- quạt không trực tiếp hút nước khỏi đất như bơm
- tác động của nó là gián tiếp và tích lũy

## 5.5 Vì sao `Temperature`, `Light` âm và `Humidity` dương

Chọn dấu như vậy rất hợp lý:

- `Temperature` tăng thì đất dễ mất nước hơn
- `Light` tăng thì bốc hơi và thoát hơi nước tăng
- `Humidity` không khí cao thì tốc độ mất nước của đất giảm

Điều hay ở đây là:

- các dấu đều có thể giải thích bằng trực giác vật lý
- điều này giúp phần `sign_ok` trong pipeline có ý nghĩa thật

## 5.6 Vì sao vẫn giữ thêm các khóa `b_temp`, `b_humi`, ...`

Trong `TRUE_PARAMS` có cả:

- `b_temp_1`, `b_temp_2`
- và `b_temp`

Đây là một lựa chọn thực dụng:

- giữ tương thích với các đoạn code hoặc tài liệu cũ
- tiện khi cần gọi nhanh một hệ số “đại diện”

Nó không ảnh hưởng mô hình ARX chính, nhưng giúp hệ linh hoạt hơn khi dùng trong tài liệu hoặc notebook khác.

## 6. Ánh xạ tháng sang mùa

Định nghĩa ở:

- [`data_generator.py#L30`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L30)

Hàm `_month_to_season()` map:

- 3, 4, 5 -> `spring`
- 6, 7, 8 -> `summer`
- 9, 10, 11 -> `autumn`
- còn lại -> `winter`

Vì sao cần mùa, trong khi đã có tháng?

- tháng là mức chi tiết cao
- mùa là mức tổng quát hơn để báo cáo

Điều này rất hữu ích trong notebook vì:

- có thể nói “mô hình đã được kiểm tra trên 4 mùa”
- dễ giải thích hơn so với liệt kê 12 tháng

## 7. Điều chỉnh setpoint theo thời gian trong ngày

Định nghĩa ở:

- [`data_generator.py#L40`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L40)

Rule:

- từ `10h` đến `<15h`: `+1`
- từ `>=20h` hoặc `<5h`: `-1`
- còn lại: `0`

## 7.1 Vì sao cần rule này

Nếu setpoint luôn cố định:

- hệ sẽ quá đều
- thiếu tính ngày đêm
- vùng vận hành thực tế bị nghèo

Việc thay đổi nhẹ setpoint theo thời gian trong ngày giúp:

- hệ có thêm variation hợp lý
- controller có thêm cơ hội đóng/ngắt actuator
- dữ liệu giàu thông tin hơn

## 7.2 Vì sao chỉ thay đổi nhẹ `±1`

Nếu thay đổi quá mạnh:

- hành vi hệ sẽ bị ép bởi setpoint nhiều hơn là bởi động học thật
- dữ liệu có thể trở nên “nhân tạo quá mức”

Chọn `±1` là đủ để:

- tạo khác biệt
- nhưng không làm méo bài toán

## 8. Khởi tạo trục thời gian và kích thước dữ liệu

Định nghĩa ở:

- [`data_generator.py#L67`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L67)

Generator:

- dùng `np.random.default_rng(seed)`
- tính `samples_per_day = 24*3600 / T_s`
- tạo `N = days * samples_per_day`
- tạo `timestamps` bằng `pd.date_range`

## 8.1 Vì sao chọn `days=365`

Một năm có giá trị vì:

- đủ 12 tháng
- đủ 4 mùa
- đủ nhiều điều kiện vận hành khác nhau

Điều này biến bài toán từ “fit trên một đoạn dữ liệu” thành:

- kiểm tra tính tổng quát theo mùa
- kiểm tra robustness của mô hình

## 8.2 Vì sao chọn `T_s=300`

`T_s = 300 s = 5 phút` là một lựa chọn hợp lý vì:

- đủ mịn để thấy động học actuator
- không quá mịn đến mức dữ liệu phình to vô ích
- phù hợp với logic “pulse 10 phút”

Thực ra 5 phút rất đẹp cho bài toán này vì:

- 10 phút tương ứng khoảng 2 bước
- lag 1 và lag 2 của ARX trở nên có nghĩa vật lý rõ hơn

## 8.3 Vì sao kiểm tra `samples_per_day >= 4`

Nếu chu kỳ lấy mẫu quá lớn:

- ta mất động học trong ngày
- mất khả năng quan sát phản ứng của actuator
- ARX trở nên vô nghĩa

Do đó check này không chỉ là check kỹ thuật, mà còn là check ý nghĩa mô hình.

## 9. `monthly_profile`: trái tim của seasonality

Định nghĩa ở:

- [`data_generator.py#L82`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L82)

Mỗi tháng có:

- `soil_low`
- `soil_high`
- `temp_offset`
- `humi_offset`
- `light_scale`

## 9.1 Vì sao không dùng một profile cố định cho cả năm

Nếu cả năm chỉ có một profile:

- metric theo tháng sẽ vô nghĩa
- model không cần học tính mùa vụ
- các biểu đồ seasonal trong notebook chỉ còn mang tính hình thức

`monthly_profile` giúp:

- tạo khác biệt rõ giữa các tháng
- nhưng khác biệt vẫn có cấu trúc, không phải random

## 9.2 Ý nghĩa của `soil_low` và `soil_high`

Hai tham số này mô tả:

- dải vận hành mong muốn của độ ẩm đất

Việc cho dải này thay đổi theo tháng phản ánh:

- mùa nóng có thể cần giữ ẩm cao hơn
- mùa mát có thể chấp nhận thấp hơn một chút

Điều này làm bài toán thực tế hơn và cũng khiến điều khiển có mục tiêu thay đổi theo mùa.

## 9.3 Ý nghĩa của `temp_offset`, `humi_offset`, `light_scale`

Ba tham số này điều chỉnh:

- nhiệt độ nền theo tháng
- độ ẩm nền theo tháng
- cường độ ánh sáng theo tháng

Điểm hay là:

- bạn không sinh mỗi biến theo một hàm độc lập hoàn toàn
- bạn cho mỗi tháng một “bản sắc khí hậu” riêng

Đây là cách rất hợp lý để tạo seasonality có cấu trúc.

## 10. Tạo setpoint theo từng thời điểm

Định nghĩa ở:

- [`data_generator.py#L97`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L97)

Từ `monthly_profile`, generator tạo:

- `soil_low_base`
- `soil_high_base`
- `seasonal_temp_offset`
- `seasonal_humi_offset`
- `seasonal_light_scale`

Sau đó cộng thêm `low_adjust` và `high_adjust` theo thời gian trong ngày để có:

- `soil_low_sp`
- `soil_high_sp`

Ý nghĩa:

- setpoint cuối cùng là kết quả của:
  - ảnh hưởng mùa
  - ảnh hưởng thời điểm trong ngày

Nó làm hệ vận hành quanh một mục tiêu không hoàn toàn tĩnh, giống nhà kính thật hơn.

## 11. Nhiễu theo ngày: vì sao phải có

Định nghĩa ở:

- [`data_generator.py#L109`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L109)

Generator tạo:

- `day_temp_offset`
- `day_humi_offset`
- `day_light_factor`
- `day_heat_boost`
- `day_dry_penalty`

## 11.1 Vì sao cần nhiễu ở cấp độ ngày

Nếu chỉ có chu kỳ ngày-đêm lặp lại hoàn hảo:

- mọi ngày sẽ giống nhau
- dữ liệu sẽ quá điều hòa
- mô hình có thể fit rất đẹp mà không thực sự học được động học đa dạng

Nhiễu cấp ngày giúp:

- mỗi ngày khác nhau một chút
- nhưng vẫn giữ cấu trúc khí hậu hợp lý

## 11.2 Vì sao có cả Gaussian lẫn lựa chọn rời rạc

Ở đây có 2 kiểu biến động:

- liên tục: `normal`, `uniform`
- rời rạc: `choice` với `heat_boost`, `dry_penalty`

Điều này hay vì:

- Gaussian tạo lệch mềm
- lựa chọn rời rạc tạo các “sự kiện” như ngày nóng đột biến hoặc ngày khô

Nhờ vậy môi trường không quá trơn.

## 12. Mô phỏng ánh sáng

Định nghĩa ở:

- [`data_generator.py#L116`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L116)

Ánh sáng được tạo bằng:

- dạng sin theo ban ngày
- cộng ambient light
- nhân seasonal scale
- cộng noise ngắn hạn
- clip vào `[0,1300]`

## 12.1 Vì sao ánh sáng dùng hàm dạng sin

Đây là lựa chọn tự nhiên vì:

- ánh sáng tăng dần sau bình minh
- đạt đỉnh ban trưa
- giảm dần về chiều

So với random, dạng sin:

- tạo cấu trúc thời gian hợp lý
- dễ giải thích
- làm `Light` thực sự trở thành một exogenous input có ý nghĩa

## 12.2 Vì sao vẫn thêm ambient light và noise

Nếu chỉ dùng sin hoàn hảo:

- tín hiệu sẽ quá sạch
- model có thể bị “học thuộc”

Ambient light và noise giúp:

- tạo độ gồ ghề thực tế
- mô phỏng mây, biến động nhỏ, nhiễu cảm biến giả lập

## 13. Mô phỏng nhiệt độ và độ ẩm ngoài trời

Định nghĩa ở:

- [`data_generator.py#L126`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L126)

`outdoor_temp` và `outdoor_humi` được xây từ:

- chu kỳ theo giờ
- offset theo ngày
- offset theo tháng
- các sự kiện rời rạc
- noise ngắn hạn

## 13.1 Vì sao `temp_phase` dịch pha về 14h

Nhiệt độ ngoài trời thường đạt cực đại trễ hơn đỉnh ánh sáng.

Việc dùng:

- `(hour - 14.0)`

là rất hợp lý vì:

- đỉnh nhiệt không trùng đúng 12h
- mô hình ngày-đêm thật hơn

## 13.2 Vì sao độ ẩm ngoài trời đi ngược phần nào với nhiệt độ

`outdoor_humi` dùng:

- `-13.0 * cos(temp_phase)`

tức là:

- khi nhiệt tăng, ẩm có xu hướng giảm
- khi nhiệt hạ, ẩm có xu hướng tăng

Đây là logic khí tượng hợp lý và tạo ra mối quan hệ tự nhiên giữa `Temperature` và `Humidity`.

## 14. Khởi tạo các biến trạng thái

Định nghĩa ở:

- [`data_generator.py#L148`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L148)

Generator khởi tạo:

- `Temp`
- `Humi`
- `Drip`
- `Mist`
- `Fan`
- `y`

và đặt:

- `Temp[0], Temp[1]` theo outdoor
- `Humi[0], Humi[1]` theo outdoor
- `y[0]=58.0`, `y[1]=57.8`

## 14.1 Vì sao khởi tạo `y` gần vùng setpoint

Chọn `58.0` và `57.8` là hợp lý vì:

- hệ bắt đầu ở trạng thái không quá khô, không quá ướt
- tránh việc đầu chuỗi bị lệch quá mạnh
- tránh tình trạng vài chục mẫu đầu chỉ để “ổn định lại hệ”

Điều này làm dữ liệu hữu ích hơn ngay từ đầu.

## 15. Minimum switching time và pulse logic

Định nghĩa ở:

- [`data_generator.py#L161`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L161)

Generator đặt:

- `min_drip_switch_steps`
- `min_mist_switch_steps`
- `min_fan_switch_steps`

đều khoảng:

- `600 / T_s`
- tức là khoảng `10 phút`

## 15.1 Vì sao cần minimum switching time

Nếu actuator được phép bật tắt liên tục từng bước:

- dữ liệu sẽ phi thực tế
- duty cycle có thể đẹp nhưng không giống hệ điều khiển thật
- ARX có thể học ra những hệ số không mang ý nghĩa vật lý

Minimum switching time giúp:

- actuator có độ “lì” hợp lý
- tín hiệu điều khiển bớt nhiễu trắng
- động học hệ phản ánh thiết bị thật hơn

## 15.2 Vì sao dùng pulse duration cho `Drip` và `Mist`

`Drip` và `Mist` là actuator kiểu pulse hợp lý hơn là bật liên tục dài.

Điều này đúng vì:

- tưới thường theo đợt
- phun sương thường theo nhịp

Nếu để actuator bật liên tục quá lâu:

- hệ dễ bị saturate
- excitation mất đa dạng

## 16. Rule điều khiển `Drip`

Định nghĩa ở:

- [`data_generator.py#L181`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L181)

Logic:

- nếu đang trong pulse thì tiếp tục
- nếu không:
  - đất đã dưới `low_sp` ít nhất 2 mẫu
  - và chưa quá gần `high_sp`
  - và đủ điều kiện switch
  - thì bật `Drip`

## 16.1 Vì sao dùng `low_count >= 2`

Nếu chỉ cần một mẫu dưới ngưỡng:

- nhiễu có thể kích hoạt tưới giả
- hệ quá nhạy

Yêu cầu 2 mẫu liên tiếp giúp:

- bớt nhạy với nhiễu
- giống một cơ chế xác nhận điều kiện

## 16.2 Vì sao thêm điều kiện `y <= high_sp - 1.0`

Điều kiện này giúp:

- tránh tưới khi đất đã gần ngưỡng trên
- giảm overshoot
- giữ hành vi hợp lý hơn

## 17. Rule điều khiển `Fan`

Định nghĩa ở:

- [`data_generator.py#L192`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L192)

Logic:

- nếu fan đang tắt:
  - bật khi nhiệt quá cao hoặc ẩm quá cao
- nếu fan đang bật:
  - tắt khi nhiệt và ẩm đã đủ thấp

Đây là hysteresis rõ ràng.

## 17.1 Vì sao dùng cả nhiệt và ẩm cho `Fan`

Fan trong nhà kính không chỉ để làm mát mà còn để:

- thông gió
- kéo ẩm xuống

Nên rule dựa trên cả `Temp` và `Humi` là hợp lý hơn nhiều so với chỉ dùng nhiệt độ.

## 18. Rule điều khiển `Mist`

Định nghĩa ở:

- [`data_generator.py#L208`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L208)

Logic:

- bật khi nhiệt cao và ẩm thấp
- tắt khi nhiệt đã hạ hoặc ẩm đã lên

Đây là rule rất hợp lý cho phun sương.

## 18.1 Vì sao `Mist` không phụ thuộc trực tiếp vào `Soil_Moisture`

Đây là điểm hay.

`Mist` được xem là actuator cho vi khí hậu:

- tác động vào `Humidity`
- gián tiếp ảnh hưởng đất

Nếu `Mist` cũng điều khiển trực tiếp theo `Soil_Moisture`, vai trò của nó sẽ chồng quá nhiều với `Drip`.

## 19. Persistent excitation an toàn

Định nghĩa ở:

- [`data_generator.py#L225`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L225)

Đây là phần cực kỳ quan trọng cho bài toán nhận dạng hệ.

Generator chèn pulse nhỏ khi:

- hệ đang ở vùng an toàn
- actuator đang tắt
- đủ điều kiện switch
- xác suất nhỏ được kích hoạt

## 19.1 Vì sao cần persistent excitation

Nếu dữ liệu quá đều:

- mô hình không phân biệt được tác động của các input
- nhiều tham số sẽ khó được nhận dạng chính xác
- hệ số có thể sai dấu hoặc kém ổn định

Persistent excitation giúp:

- làm tín hiệu điều khiển đa dạng hơn
- tăng khả năng quan sát phản ứng của hệ
- cải thiện identifiability

## 19.2 Vì sao excitation phải “an toàn”

Nếu random bật actuator bất cứ lúc nào:

- hệ bị phá cấu trúc điều khiển
- dữ liệu trông giả
- notebook khó thuyết phục

Do đó excitation được chèn:

- trong khoảng vận hành hợp lý
- với xác suất thấp
- và vẫn tôn trọng minimum switching time

Đây là một quyết định rất đúng.

## 20. Động học nhiệt và ẩm bên trong nhà kính

Định nghĩa ở:

- [`data_generator.py#L262`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L262)

Phương trình:

```text
Temp[i] = 0.86 * Temp[i-1] + 0.14 * outdoor_temp[i] - 1.35 * Fan[i] - 1.40 * Mist[i] + noise
Humi[i] = 0.84 * Humi[i-1] + 0.16 * outdoor_humi[i] + 11.0 * Mist[i] - 3.8 * Fan[i] + noise
```

## 20.1 Vì sao không cho `Temp` và `Humi` bằng ngay outdoor

Nếu làm vậy:

- nhà kính sẽ không còn là hệ có quán tính
- các actuator mất vai trò động học
- dữ liệu quá đơn giản

Hệ số `0.86/0.14` và `0.84/0.16` thể hiện:

- trạng thái trong nhà kính phụ thuộc chủ yếu vào trạng thái trước đó
- nhưng vẫn bị kéo bởi môi trường ngoài

Đây là mô hình quán tính rất hợp lý.

## 20.2 Vì sao `Mist` làm giảm nhiệt nhưng tăng ẩm

Điều này sát thực tế:

- phun sương làm bay hơi nước
- tăng ẩm không khí
- có thể kéo nhiệt xuống chút ít

## 20.3 Vì sao `Fan` làm giảm cả nhiệt lẫn ẩm

Fan:

- tản nhiệt
- tăng trao đổi khí
- kéo ẩm không khí xuống

Do đó dấu âm ở cả hai phương trình là hợp lý.

## 21. Sinh `Soil_Moisture` theo phương trình ARX thật

Định nghĩa ở:

- [`data_generator.py#L280`](C:/Users/minht/OneDrive/Desktop/ARX-Model/data_generator.py#L280)

Đây là chỗ kết nối tất cả mọi thứ:

- trạng thái đất quá khứ
- nhiệt độ nhà kính
- độ ẩm nhà kính
- ánh sáng
- trạng thái actuator
- noise quá trình

Điều hay là:

- đầu vào của phương trình ARX không phải tín hiệu ngoài trời thô
- mà là tín hiệu đã được biến đổi qua logic môi trường và điều khiển

Điều này làm bài toán có ý nghĩa hơn rất nhiều.

## 21.1 Vì sao clip `y` vào `[10,100]`

Clip giúp:

- tránh giá trị vô lý
- giữ dữ liệu trong miền vận hành
- tránh một vài mẫu dị làm méo metric

Nếu không clip, đôi khi noise + actuator có thể tạo ra giá trị quá phi thực tế.

## 22. Các cột xuất ra cuối cùng

Generator trả về dataframe gồm:

- `Timestamp`
- `Month`
- `Season`
- `Soil_Moisture`
- `Soil_Low_SP`
- `Soil_High_SP`
- `Temperature`
- `Humidity`
- `Light`
- `Drip`
- `Mist`
- `Fan`

Đây là thiết kế rất tốt vì:

- vừa có biến mục tiêu
- vừa có input
- vừa có metadata để làm báo cáo

Notebook vì thế mới có thể làm được:

- chart theo tháng
- chart theo mùa
- duty cycle
- setpoint occupancy

## 23. Vì sao generator này phù hợp cho ARX(2,2,1)

Generator này được “đóng khung” rất hợp với baseline vì:

- output thật có 2 lag
- mỗi input có 2 lag
- input delay thực chất bắt đầu từ `t-1`
- động học đủ tuyến tính cục bộ để OLS học được
- nhưng vẫn đủ phong phú để 1-step và free-run không trùng nhau

Nói cách khác:

- đây không phải dữ liệu được tạo để mô hình thắng dễ dàng
- mà là dữ liệu được tạo để mô hình ARX có cơ hội thể hiện đúng năng lực của nó

## 24. Những điểm generator làm rất đúng

### 24.1 Có cấu trúc vật lý rõ

- dấu của tham số hợp lý
- actuator có vai trò tách biệt
- có quán tính

### 24.2 Có logic điều khiển

- hysteresis
- minimum switching time
- pulse logic

### 24.3 Có tính mùa vụ

- theo tháng
- theo ngày đêm

### 24.4 Có excitation phục vụ nhận dạng

- không quá đều
- không phá cấu trúc

### 24.5 Có ground truth để đánh giá mô hình

- rất tốt cho đồ án nhận dạng hệ

## 25. Những điểm bạn có thể nói khi bảo vệ

Nếu giảng viên hỏi vì sao generator không random đơn giản, bạn có thể trả lời:

> Vì nếu chỉ random các tín hiệu đầu vào thì dữ liệu có thể nhiều nhưng không có logic vận hành. Em muốn bộ dữ liệu vừa có ý nghĩa vật lý, vừa có excitation đủ cho nhận dạng ARX, nên em thêm setpoint, hysteresis, minimum switching time, biến thiên theo mùa và excitation an toàn.

Nếu bị hỏi vì sao chọn ARX(2,2,1), bạn có thể nói:

> Em chủ động thiết kế generator theo đúng tinh thần ARX(2,2,1): output có hai bậc nhớ, mỗi input có hai lag tác động, và delay bắt đầu từ t-1. Nhờ đó khi mô hình thu hồi đúng 14/14 dấu tham số thì kết quả có ý nghĩa thật chứ không chỉ là fit số.

Nếu bị hỏi vì sao thêm persistent excitation, bạn có thể nói:

> Nếu actuator chỉ chạy đúng theo điều kiện điều khiển cơ bản thì một số tín hiệu có thể quá đều, làm bài toán nhận dạng kém giàu thông tin. Em chèn excitation nhỏ nhưng chỉ ở vùng an toàn để tăng khả năng nhận dạng mà không phá vỡ logic hệ.

## 26. Hạn chế của generator hiện tại

Dù generator khá tốt, vẫn có một số hạn chế:

- vẫn là synthetic data
- nhiều quan hệ còn tuyến tính hóa mạnh
- chưa mô phỏng đầy đủ các tương tác phi tuyến phức tạp của nhà kính thật
- một số ngưỡng điều khiển vẫn mang tính heuristic

Tuy nhiên, với mục tiêu của đồ án ARX baseline, các hạn chế này là chấp nhận được, vì:

- baseline cần dữ liệu đủ sạch để đánh giá đúng bản chất mô hình
- chưa phải giai đoạn xây digital twin siêu thực

## 27. Kết luận

`data_generator.py` của bạn là một generator được thiết kế có chủ đích và khá thông minh.

Điểm mạnh nhất của nó là:

- không sinh dữ liệu ngẫu nhiên vô nghĩa
- mà tạo ra một hệ có logic vận hành, logic mùa vụ, logic điều khiển và logic nhận dạng

Nó thành công ở 4 mục tiêu cùng lúc:

1. làm dữ liệu có vẻ hợp lý về vật lý
2. làm dữ liệu đủ giàu để nhận dạng ARX
3. giữ được ground truth để so sánh
4. tạo nền rất tốt cho báo cáo và notebook

Nếu cần nói ngắn gọn bằng một câu:

> Generator này được thiết kế không phải để “bơm ra dữ liệu”, mà để xây một nhà kính mini giả lập đủ hợp lý, đủ giàu thông tin, và đủ công bằng để kiểm tra chất lượng của baseline ARX(2,2,1).
