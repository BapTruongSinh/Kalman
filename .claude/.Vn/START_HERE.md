# BẮT ĐẦU Ở ĐÂY — Thiết Lập Template Dự Án

> **Đây là template, không phải dự án thật.**
> Mọi giá trị placeholder (được bọc trong `[ngoặc vuông]`) phải được thay bằng thông tin dự án thật trước khi bắt đầu phát triển.
> Không bắt đầu viết code cho đến khi onboarding hoàn tất và user đã xác nhận documentation.

---

## Dành Cho Claude: Onboarding Protocol

Khi user nói **"START!"**, hãy thực hiện đầy đủ trình tự onboarding này. Không chờ chỉ dẫn tiếp theo, bắt đầu ngay lập tức. Không bỏ qua phase hoặc gộp phase.

---

### Phase 1: Thu Thập Thông Tin Dự Án

Hỏi user theo từng nhóm hội thoại, mỗi lần 3 đến 4 câu hỏi. Chờ câu trả lời trước khi chuyển sang nhóm tiếp theo. Không đưa toàn bộ câu hỏi cùng một lúc.

**Nhóm 1 — Thông tin cơ bản của dự án:**
1. Tên dự án là gì?
2. Dự án làm gì trong một câu?
3. Người dùng chính là ai? (ví dụ: "chủ doanh nghiệp nhỏ", "đội vận hành nội bộ", "developer")
4. Dự án giải quyết vấn đề gì, hiện nay người dùng đang làm gì khi chưa có nó?

**Nhóm 2 — Tech stack:**
5. Công nghệ frontend là gì? (ví dụ: Next.js, React + Vite, Vue, không có)
6. Backend là gì? (ví dụ: Next.js API routes, Express, FastAPI, Django)
7. Database là gì? (ví dụ: PostgreSQL, MySQL, SQLite, MongoDB)
8. ORM hoặc query layer là gì? (ví dụ: Prisma, Drizzle, SQLAlchemy, raw SQL)
9. Mục tiêu hosting/deployment là gì? (ví dụ: Railway, Vercel, Fly.io, AWS)
10. Package manager là gì? (npm / pnpm / yarn)
11. Node version là gì, nếu có? (kiểm tra `.nvmrc` nếu tồn tại)

**Nhóm 3 — Convention:**
12. Formatter và linter là gì? (ví dụ: Prettier + ESLint, Biome)
13. Test runner cho unit test là gì? (ví dụ: Vitest, Jest)
14. Các command dev / build / test là gì? (ví dụ: `npm run dev`, `npm run build`, `npm test`)

**Nhóm 4 — Yêu cầu sản phẩm:**
15. Những tính năng chính mà sản phẩm phải có trong v1 là gì? Hãy liệt kê chúng; bạn sẽ chuyển chúng thành yêu cầu FR-XXX trong PRD.
16. Có yêu cầu phi chức năng nào không? (ví dụ: mục tiêu hiệu năng, mức accessibility, hỗ trợ trình duyệt)
17. Điều gì rõ ràng nằm ngoài phạm vi v1? (quan trọng để giữ backlog tập trung)
18. Product owner / người ra quyết định là ai?

**Nhóm 5 — Content & SEO (bỏ qua nếu đây là tool nội bộ không có trang public-facing):**
19. Sản phẩm có website public-facing, landing page, hoặc marketing content không?
20. Bạn có brand voice hoặc tone đã định nghĩa không? (ví dụ: "chuyên nghiệp và trực tiếp", "thân thiện và hội thoại") Có ví dụ văn bản hoặc style guide nào không?
21. Có mục tiêu SEO không? (ví dụ: mục tiêu organic traffic, keyword cụ thể muốn rank, trang đối thủ muốn vượt qua)
22. Bạn đã có copy cho trang nào chưa, hay mọi trang đều bắt đầu từ đầu?

**Nhóm 6 — Mục tiêu và câu hỏi mở:**
23. Thành công trông như thế nào? Có metric cụ thể không? (ví dụ: "100 user trong tháng đầu", "onboarding dưới 5 phút")
24. Có quyết định nào chưa được chốt không? (ví dụ: auth provider, payment processor, tích hợp bên thứ ba)

---

### Phase 2: Điền Documentation

#### 2.0 — Copy template vào đúng chỗ

Trước khi điền bất kỳ documentation nào, copy các template trống từ `.claude/templates/` tới vị trí dự án:

```
.claude/templates/docs/technical/ARCHITECTURE.md    →  docs/technical/ARCHITECTURE.md
.claude/templates/docs/technical/DESIGN_SYSTEM.md   →  docs/technical/DESIGN_SYSTEM.md
.claude/templates/docs/technical/DECISIONS.md       →  docs/technical/DECISIONS.md
.claude/templates/docs/technical/API.md             →  docs/technical/API.md
.claude/templates/docs/technical/DATABASE.md        →  docs/technical/DATABASE.md
.claude/templates/docs/user/USER_GUIDE.md           →  docs/user/USER_GUIDE.md
.claude/templates/docs/content/CONTENT_STRATEGY.md  →  docs/content/CONTENT_STRATEGY.md
.claude/templates/README.md                         →  README.md  (README của dự án, thay thế bản của template)
```

Tạo thư mục cha nếu cần. Không chỉnh sửa các file trong `.claude/templates/`; chúng là bản gốc upstream.

`CLAUDE.md` và `PRD.md` đã có ở project root và không cần copy.

Dùng các câu trả lời đã thu thập ở Phase 1 để cập nhật các file sau theo thứ tự. Thay mọi `[placeholder]` bằng nội dung thật. Nếu user chưa biết câu trả lời, dùng `[TBD]`; không bao giờ để lại placeholder gốc của template.

**2.1 — `CLAUDE.md`**

- Tên dự án (heading và đoạn context)
- Mô tả context dự án trong 2-3 câu
- Dòng tóm tắt tech stack
- Phần code style: formatter, linter, import style
- Testing conventions: runner, file pattern, command
- Environment commands: dev, build, test, lint, typecheck
- Dòng stack trong header

**2.2 — `README.md`** *(được copy từ `.claude/templates/README.template.md` ở bước 2.0)*

- Tên dự án và mô tả một câu
- Các đoạn overview (nó làm gì, dành cho ai, vì sao tồn tại)
- Bảng tech stack: điền mọi layer
- Getting Started: prerequisite, bước install, command chạy
- Bảng environment variable: liệt kê mọi biến bắt buộc đã biết kèm mô tả (không ghi giá trị)

**2.3 — `PRD.md`**

- Executive summary (3-5 câu từ mô tả dự án và mục tiêu)
- Problem statement: tình hình hiện tại, vấn đề, vì sao là bây giờ
- User persona: một section cho mỗi loại user được nhắc tới, gồm vai trò, mục tiêu, pain point, trình độ kỹ thuật
- Functional requirements: chuyển danh sách tính năng thành các item đánh số `FR-001`, `FR-002`, ... Nhóm theo feature area. Hãy cụ thể; mỗi FR nên là một statement có thể test.
- Non-functional requirements: điền hiệu năng, bảo mật, accessibility, hỗ trợ trình duyệt
- Out of scope: liệt kê mọi điều user nói không thuộc v1
- Open questions: liệt kê mọi quyết định chưa giải quyết từ Nhóm 5
- Revision history: thêm entry đầu tiên với ngày hôm nay

**2.4 — `docs/technical/ARCHITECTURE.md`**

- Bảng tech stack: điền mọi layer với version và lý do ngắn
- Bảng infrastructure environment: tối thiểu có hàng Production và Local
- Để nguyên các section Frontend Architecture, Backend Architecture, và Data Flow như template; chúng sẽ được điền dần khi implementation tiến triển
- Section **Design system and UX** chỉ link tới `DESIGN_SYSTEM.md`; không duplicate token ở đó

**2.4b — `docs/technical/DESIGN_SYSTEM.md`**

- Để nguyên các bảng token, component inventory, interaction pattern, và key user flow như template; @ui-ux-designer sẽ điền khi UI sản phẩm tiến triển (song song với cách copy tiến triển trong `CONTENT_STRATEGY.md`)

**2.5 — `docs/technical/DECISIONS.md`**

Điền ADR-001 với quyết định tech stack ban đầu:
- Context: loại dự án, quy mô/mức quen thuộc của team, ràng buộc deployment
- Options considered: liệt kê 2-3 phương án thay thế thực tế đã được đánh giá (hoặc có thể đã được đánh giá)
- Decision: stack đã chọn và lý do chính
- Consequences: điều gì trở nên dễ hơn, trade-off nào được chấp nhận

Cập nhật bảng Decision Index với dòng ADR-001.

**2.6 — `docs/content/CONTENT_STRATEGY.md`** *(bỏ qua nếu dự án không có trang public-facing; trong trường hợp đó đánh dấu file là `[N/A — internal tool]`)*

Dùng câu trả lời từ Nhóm 5:
- Overview và primary value proposition: câu duy nhất mà mọi copy phải củng cố
- Bảng Brand Voice: điền bốn chiều giọng nói (formality, energy, personality, authority) dựa trên tone user mô tả; nếu chưa định nghĩa tone, để là `[TBD — define with @copywriter-seo]`
- Tone-by-context matrix: tối thiểu điền hàng marketing headline và error message; các hàng khác để `[TBD]`
- Target personas: một entry cho mỗi persona từ PRD.md, tóm tắt job-to-be-done và objection lớn nhất theo góc nhìn copy
- Keyword strategy: liệt kê keyword cụ thể user nhắc tới; đánh dấu volume và difficulty là `[verify]`; các dòng còn lại để `[TBD]`
- Canonical domain: điền domain chính và lựa chọn www/non-www nếu biết; nếu không thì `[TBD]`
- Để Page Copy Library, CTA Library, và Redirect Map là template trống; @copywriter-seo sẽ điền khi viết page

---

### Phase 3: Xây Backlog Ban Đầu

Đây là bước quan trọng. **TODO.md không được để lại các item placeholder.** Backlog là hàng đợi công việc của team; nó phải phản ánh các task thật, có thể hành động trước khi bắt đầu phát triển.

#### 3.1 — Suy ra task từ PRD

Đọc các functional requirement trong `PRD.md` và chia chúng thành task cụ thể, có thể implement. Với mỗi feature area, suy nghĩ end-to-end xem cần những gì:

- Có cần database schema không? → task gắn tag `[area: database]`
- Có cần API endpoint không? → task gắn tag `[area: backend]`
- Có cần UI không? → task gắn tag `[area: frontend]`
- Có cần UX design trước không? → task gắn tag `[area: design]`
- Có cần E2E test không? → task gắn tag `[area: qa]`
- Đây có phải trang public-facing cần copy và SEO không? → task gắn tag `[area: content]`; copy và keyword work phải đi trước frontend task cho trang đó

#### 3.2 — Quy tắc sizing và sắp thứ tự task

- Mỗi task nên đại diện cho một đơn vị công việc có ý nghĩa, có thể hoàn thành độc lập, thứ mà một specialist agent có thể xử lý trong một session tập trung
- Không tạo task quá lớn chứa nhiều concern ("xây toàn bộ auth system"); hãy chia nhỏ
- Không tạo task quá nhỏ đến mức tầm thường ("thêm một button"); hãy gom chúng lại
- Sắp theo dependency: task chặn task khác đưa vào "Up Next" trước
- Các task đầu tiên thường có của dự án mới là: thiết kế schema ban đầu (`database`), sau đó core API endpoint (`backend`), rồi core UI (`frontend`)
- Nếu feature nào cần design spec trước khi implement, tạo design task đi trước frontend task

#### 3.3 — Viết task

Với mỗi task:

**Bước A — Thêm vào `TODO.md`** theo format:
```
- [ ] #NNN — Mô tả rõ, tập trung vào outcome [area: tag] → [.tasks/NNN-short-title.md](.tasks/NNN-short-title.md)
```

Đặt vào section phù hợp:
- **Up Next**: 3-5 task đầu tiên sẵn sàng bắt đầu ngay, sắp theo dependency và priority
- **Backlog**: mọi task còn lại, sắp tương đối theo thời điểm sẽ cần

**Bước B — Tạo `.tasks/NNN-short-title.md`** bằng cách copy `.tasks/TASK_TEMPLATE.md`:
- Đổi tên file để khớp task number và title kebab-case ngắn (ví dụ: `003-user-auth-schema.md`)
- Điền mọi field frontmatter:
  - `id`, `title`, `status: "todo"`, `area`, `agent` (specialist agent sẽ làm việc này)
  - `created_at` (ngày hôm nay)
  - `prd_refs`: liệt kê các số FR-XXX mà task này đáp ứng
  - `blocks` và `blocked_by`: xác định dependency giữa các task
  - `priority`: "high" cho item Up Next, "normal" hoặc "low" cho Backlog
- Viết `## Description` chi tiết, 2-5 câu giải thích cần làm gì và vì sao
- Viết `## Acceptance Criteria` cụ thể, là các statement có thể test để định nghĩa "done"
- Thêm `## Technical Notes` nếu biết (ADR liên quan, dependency schema, API contract cần thiết)
- Thêm entry tạo task vào bảng `## History`

**Bước C — Xóa mọi item placeholder còn lại** khỏi `TODO.md` (các entry `#001` đến `#008` đi kèm template). Thay toàn bộ bằng task thật suy ra từ PRD. Không giữ item placeholder.

#### 3.4 — Đánh dấu #000 là nền tảng

Task `#000` (initial project setup) đã hoàn thành. Giữ nó trong section Completed. Task tiếp theo bắt đầu từ `#001`.

---

### Phase 4: Review Với User

Sau khi hoàn tất toàn bộ documentation và backlog ban đầu, trình bày summary có cấu trúc:

**Format summary:**

```
## Onboarding Complete — Đây là những gì đã được thiết lập:

### Dự án
[Tên] — [mô tả một câu]

### Documentation đã điền
- CLAUDE.md — stack, convention, command
- README.md — overview, getting started, env vars
- PRD.md — [X] functional requirement trên [Y] feature area, [Z] persona
- ARCHITECTURE.md — tech stack và infrastructure
- DESIGN_SYSTEM.md — design/UX template đã sẵn sàng (được @ui-ux-designer tinh chỉnh khi UI ship)
- DECISIONS.md — ADR-001: [tên quyết định tech stack]
- CONTENT_STRATEGY.md — [đã điền brand voice / keyword target | đánh dấu N/A cho tool nội bộ]

### Backlog ban đầu
Up Next ([N] task):
  #001 — [title] [area]
  #002 — [title] [area]
  ...

Backlog ([N] task):
  #NNN — [title] [area]
  ...

### Open item cần quyết định
- [Mọi item [TBD] hoặc câu hỏi mở từ PRD]

Mọi thứ có đúng không? Có cần chỉnh gì trước khi bắt đầu build không?
```

Thực hiện mọi chỉnh sửa user yêu cầu. Chạy lại các cập nhật file bị ảnh hưởng.

---

### Phase 5: Xóa File Này

Khi user xác nhận rõ họ hài lòng:

1. Xóa `START_HERE.md`
2. Xác nhận: "Setup complete. START_HERE.md has been removed. Say 'what's next?' and I'll walk you through the first task."

Không xóa file này trước khi user nói họ hài lòng. "Looks good" hoặc "yes" được tính là xác nhận.

---

## Onboarding Checklist

Dùng checklist này để xác minh mọi thứ đã xong trước khi xin xác nhận ở Phase 4.

**Documentation**
- [ ] Template đã được copy từ `.claude/templates/` tới `docs/` và `README.md` (bước 2.0)
- [ ] `CLAUDE.md`: mọi placeholder đã được thay, không còn `[square brackets]` (hoặc được đánh dấu rõ là `[TBD]`)
- [ ] `README.md`: mọi placeholder đã được thay (copy từ `.claude/templates/README.md`)
- [ ] `PRD.md`: executive summary, persona, yêu cầu FR-XXX đã đánh số, NFR, out of scope, open questions
- [ ] `docs/technical/ARCHITECTURE.md`: bảng tech stack và infrastructure environment đã điền
- [ ] `docs/technical/DESIGN_SYSTEM.md`: đã copy từ template (bảng placeholder OK cho đến khi design work bắt đầu)
- [ ] `docs/technical/DECISIONS.md`: ADR-001 đã điền bằng rationale tech stack thật
- [ ] `docs/content/CONTENT_STRATEGY.md`: brand voice và persona đã điền (hoặc đánh dấu `[N/A]` nếu là tool nội bộ không có trang public-facing)

**Backlog**
- [ ] `TODO.md` chỉ chứa task thật, không còn entry placeholder `#001`-`#008`
- [ ] Mọi TODO item đều có file `.tasks/NNN-*.md` tương ứng
- [ ] Mọi file `.tasks/NNN-*.md` có: description, acceptance criteria, `prd_refs`, `agent`, `created_at`
- [ ] Dependency `blocks` / `blocked_by` được set đúng khi task phụ thuộc nhau
- [ ] "Up Next" chứa các task đầu tiên sẵn sàng bắt đầu, sắp theo dependency
- [ ] Task #000 vẫn nằm trong Completed

**Sign-off**
- [ ] Summary đã được trình bày cho user (Phase 4)
- [ ] User đã xác nhận hài lòng
- [ ] File này đã được xóa
