# SOUL.md

*Điều template này tin tưởng, điều nó từ chối, và lý do nó được xây theo cách hiện tại.*

---

## Vấn Đề Nó Giải Quyết

AI agent rất mạnh, nhưng bản chất dễ hỗn loạn. Nếu không có ràng buộc, một AI đơn lẻ khi nhận yêu cầu "xây cho tôi một sản phẩm" sẽ bỏ qua kiến trúc, quên design system, tự bịa schema database trong lúc làm, để documentation ở mức ý định tốt đẹp, và đẩy code có thể chạy về mặt kỹ thuật nhưng chưa từng được kiểm thử theo đúng các yêu cầu mà nó phải đáp ứng.

Template này là câu trả lời cho vấn đề đó. Nó áp đặt một cấu trúc gồm chuyên môn hóa, trình tự, quyền sở hữu và rule, để AI có thể đi nhanh mà không để lại một vệt nợ kỹ thuật phía sau.

---

## Mô Hình Crew

Ý tưởng trung tâm ở đây là chuyên môn hóa.

Một AI toàn năng cố làm mọi thứ sẽ tạo ra mọi thứ ở mức trung bình. Mười hai agent tập trung, mỗi agent có domain rõ ràng, tập tài liệu mình sở hữu, và protocol mình tuân theo, sẽ tạo ra công việc mạch lạc và chuyên nghiệp. Systems architect không chạm vào frontend. Copywriter không chạm vào database. QA engineer không quyết định thiết kế API. Mỗi người ở đúng lane của mình, và khi cộng các lane lại thì thành một sản phẩm.

Đây không phải là giới hạn. Đây là cách các team tốt làm việc. Một đoàn phim không để một người vừa quay camera, vừa viết kịch bản, vừa soạn nhạc, vừa lo hậu cần cùng lúc. Đạo diễn không ứng biến phần cinematography. Ranh giới là thứ cho phép đi sâu.

Crew ở đây có mười hai người. Một agent chạy trên Opus vì các quyết định kiến trúc cần nhiều cân nhắc hơn mọi thứ khác. Phần còn lại chạy trên Sonnet. Documentation writer chạy trên Haiku, vì viết user guide cần sự rõ ràng chứ không cần compute lớn.

---

## Template Này Tin Điều Gì

**Thiết kế trước khi code.**
Architect phác thảo, designer đặc tả, rồi builder mới xây. Copy được viết trước khi marketing page tồn tại. Schema được review trước khi migration chạy. Đảo ngược trình tự này là cách tích lũy các sửa chữa đắt đỏ thay vì các chỉnh sửa rẻ.

**Con người quyết định; agent thực thi.**
PRD là read-only. Ba lớp bảo vệ nó: warning block trong tài liệu, rule trong CLAUDE.md, và constraint trong system prompt của mọi agent. Backlog thuộc về con người. Agent là executor có quan điểm: chúng phản biện ý tưởng tệ, flag scope creep, và tạo ra sản phẩm chuyên nghiệp, nhưng chúng không đặt hướng đi. Việc đó là của bạn.

**Documentation không phải việc làm sau.**
Một feature không cập nhật documentation là một feature chưa hoàn tất. Không phải hoàn thành 90%, mà là chưa hoàn tất. Thư mục `docs/` không phải nghĩa địa của ý định. Nó là một hệ thống sống. Mỗi tài liệu có owner được tuyên bố rõ. Owner cập nhật tài liệu của mình trước khi đánh dấu task done, không phải sau sprint sau, không phải "sớm thôi".

**Test là yêu cầu, không phải chỉ số coverage.**
QA engineer viết test theo các identifier `FR-XXX` trong PRD, không theo chi tiết implementation, cũng không phải để đạt con số 80% line coverage. Test không truy vết tới yêu cầu là nhiễu. Test truy vết tới yêu cầu là bằng chứng rằng thứ đó đã được xây đúng.

**Tay nghề ở mọi layer.**
Template này nêu rõ các anti-pattern. UI/UX designer được dặn: không dùng purple gradient trên nền trắng, không dùng Space Grotesk làm typeface chính, không dùng layout rập khuôn dễ đoán. Docker expert xây container non-root với read-only filesystem. CI/CD engineer chạy security scan trên mọi push. Database expert dùng `EXPLAIN ANALYZE` trước khi gọi một query là xong. Không layer nào được phép chỉ "đủ dùng". Mọi layer đều là cơ hội để làm có chủ ý.

**Niềm tin thông qua minh bạch.**
Quyết định kiến trúc không chỉ được ghi lại, mà được ghi lại cùng trade-off. Không phải "chúng ta chọn PostgreSQL", mà là "chúng ta chọn PostgreSQL vì X, đã cân nhắc Y, và chấp nhận Z là hệ quả." ADR là append-only. Khi quyết định thay đổi, ADR mới supersede ADR cũ; ADR cũ vẫn ở đó. Lịch sử chính là niềm tin.

**Bảo mật, accessibility và performance là nền sàn.**
WCAG 2.1 AA không phải điều nên có. OWASP Top 10 không phải chuyện chỉ audit mới quan tâm. Core Web Vitals (LCP < 2,5s, INP < 100ms, CLS < 0,1) không phải mục tiêu mơ ước. Đây là baseline, mức tối thiểu mà thấp hơn nó thì công việc chưa hoàn tất. Template đưa chúng vào mặc định để không thể bị quên.

---

## Template Này Từ Chối Điều Gì

**Bản năng "cứ xây đi".** Bỏ qua giai đoạn thiết kế để code sớm hơn là một khoản vay với lãi suất rất tệ. Template này bắt bạn chậm lại trước khi tăng tốc.

**Documentation viết hồi tố.** Docs viết sau khi xong việc mô tả thứ đã xây, không phải thứ dự định xây hoặc điều người dùng cần biết. Template này xem documentation là một phần của build, không phải annotation.

**Scope creep ngụy trang thành tiến độ.** PRD có phần Out of Scope là có lý do. Backlog tồn tại để ý tưởng tốt có chỗ nằm ngoài sprint hiện tại. Nói "chưa phải lúc" là một feature, không phải thất bại.

**Shortcut có hậu quả.** Bỏ qua pre-commit hook, merge khi chưa có test, viết migration gây downtime trong khi có pattern zero-downtime, tất cả đều không chấp nhận được. Template không làm cho việc né kỷ luật trở nên dễ dàng.

**Output chung chung.** Danh sách aesthetic anti-pattern trong UI/UX agent tồn tại vì thiết kế AI chung chung là vấn đề thật. Bảng màu nhút nhát, typeface bị lạm dụng, layout dễ đoán, tất cả truyền đi tín hiệu rằng không ai thực sự đưa ra lựa chọn có cân nhắc. Template này yêu cầu các lựa chọn có cân nhắc.

**Agent vượt quyền.** Specialist agent không chỉnh sửa tài liệu mà mình không sở hữu. Backend developer không cập nhật user guide. Copywriter không sửa schema. Systems architect không implement feature. Vượt quyền là cách coherence sụp đổ.

---

## Giọng Nói Phía Sau Nó

Commit message trong chính lịch sử của template này đã nói lên điều đó. Agent không chỉ được *thêm vào*, mà được *tuyển dụng*. Một mobile developer không được giới thiệu, mà một chiếc điện thoại được *trao cho thành viên mới nhất của crew*. Orchestrator không chỉ được viết, nó trở thành *một conductor đọc score trước*. Documentation writer có *trí nhớ dài hạn*. CI/CD engineer là một *pipeline whisperer*.

Đây không phải trang trí. Nó phản ánh niềm tin rằng công việc xây dựng phần mềm, kể cả infrastructure, kể cả configuration, xứng đáng với cùng mức craft như chính thứ đang được xây. Tên gọi quan trọng. Commit message được con người đọc. Template tự nó có cá tính, và các dự án xây trên nó nên thừa hưởng một phần điều đó.

Mục tiêu chưa bao giờ là tạo ra một scaffold. Mục tiêu là tạo ra một cách làm việc: một cách tôn trọng độ phức tạp của phần mềm, giá trị của phán đoán con người, và sức mạnh thật sự của AI khi nó được trao cấu trúc thay vì chỉ được trao tự do.

---

*Đọc `README.md` để biết template này làm gì. Đọc `CLAUDE.md` để biết nó hoạt động như thế nào. Đọc file này khi bạn muốn hiểu vì sao.*
