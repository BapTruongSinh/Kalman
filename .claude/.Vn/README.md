# Claude Development Template

![Claude Development Template](.assets/cover.png)

Một template khởi tạo cho dự án phần mềm được xây bằng [Claude Code](https://claude.com/product/claude-code). Dùng nó như GitHub template, chạy **`/start`**, và Claude sẽ dẫn bạn qua toàn bộ quá trình thiết lập documentation trước khi viết một dòng code nào.

Template này cũng là một **Claude Code plugin**: kiến thức domain được mã hóa thành các skill có thể gọi, thay vì nhúng trực tiếp vào system prompt của agent. Cài một lần, các skill sẽ sẵn sàng trong mọi phiên Claude Code.

---

## Cài Đặt Như Plugin

Để các domain skill có sẵn toàn cục trong Claude Code:

```bash
git clone https://github.com/josipjelic/orchestrated-project-template
ln -sf "$(pwd)/orchestrated-project-template/.claude" ~/.claude/plugins/orchestrated-template
```

Chỉ vậy là đủ. Mười một domain skill (`frontend`, `backend`, `database`, `mobile`, `design`, `content`, `quality`, `docs`, `cicd`, `docker`, `planning`) sẽ xuất hiện ngay trong danh sách skill của Claude Code.

Để cập nhật:

```bash
cd orchestrated-project-template && git pull
```

Symlink giúp bạn luôn chạy từ phiên bản mới nhất.

---

## Dùng Như Project Template

### 1. Tạo repository mới từ template này

Nhấn **"Use this template"** → **"Create a new repository"** trên GitHub.

Hoặc dùng GitHub CLI:

```bash
gh repo create my-project --template https://github.com/josipjelic/orchestrated-project-template --private --clone && cd my-project
```

### 2. Xác thực GitHub CLI (tùy chọn)

```bash
gh auth login
```

Agent dùng trực tiếp `gh` cho các thao tác GitHub. Thiết lập một lần và được giữ lại qua các session. Bỏ qua nếu bạn không cần tích hợp GitHub.

### 3. Mở trong Claude Code và chạy `/start`

Claude đọc `START_HERE.md` và bắt đầu trình tự onboarding: thu thập chi tiết dự án, điền placeholder trong documentation, và xây backlog ban đầu từ yêu cầu của bạn. Cuối quá trình, `/start` tự cài plugin.

### 4. Bắt đầu build

Khi onboarding hoàn tất, `START_HERE.md` sẽ bị xóa. Dùng `TODO.md` cho backlog, hoặc chạy `/status` để xem tổng quan sức khỏe dự án.

---

## Đây Là Gì

Một scaffold dự án có quan điểm rõ ràng, cung cấp cho Claude mọi thứ cần thiết để hành động như một team phát triển mạch lạc ngay từ ngày đầu:

- **5 agent hợp nhất** bao phủ mọi discipline; mỗi agent được thiết kế mỏng, gọi domain skill thay vì mang kiến thức trong system prompt
- **11 domain skill** mã hóa kiến thức craft: protocol làm việc, framework quyết định, checklist, anti-pattern; được load theo nhu cầu, không làm phình base context
- **Lifecycle hook** chạy tự động: chặn command phá hoại, tự format khi lưu, cảnh báo khi docs lệch khỏi code
- **MCP server** được cấu hình sẵn cho live library documentation và structured reasoning, được chia sẻ trong team qua `.mcp.json` đã commit
- **File-scoped rule** chỉ inject chuẩn TypeScript, migration, và test khi file liên quan đang mở
- **Living documentation** mà agent giữ cập nhật khi dự án tiến triển
- **Product requirements document** được bảo vệ khỏi chỉnh sửa ngoài ý muốn
- **Backlog** để agent tham chiếu khi bạn hỏi "tiếp theo nên làm gì?"

---

## Commands

### `/start`

Chạy một lần sau khi tạo dự án mới. Claude đọc `START_HERE.md`, thu thập chi tiết dự án, copy template vào đúng chỗ, điền mọi placeholder, xây backlog ban đầu, và tự cài plugin.

### `/orchestrate <task description>`

Chuyển giao một multi-agent task và để Claude điều phối thực thi. Orchestrator phân tích task, xác định agent cần thiết, xác định thứ tự thực thi (song song khi an toàn, tuần tự khi có dependency), đăng ký công việc vào backlog, tạo feature branch, và chạy agent theo từng wave.

```
/orchestrate add user authentication with email and password
```

Trình bày wave plan để phê duyệt trước khi chạy bất cứ thứ gì. Dừng lại và hỏi nếu một wave thất bại.

### `/status`

Hiển thị project health card trực tiếp: branch hiện tại, task đang làm, commit gần đây, PR đang mở, blocker. Chỉ đọc, hoàn tất trong vài giây.

### `/sync-template`

Kéo thư mục `.claude/` mới nhất từ upstream template vào dự án của bạn. Hiển thị diff và hỏi xác nhận. File local-only không bao giờ bị xóa.

---

## Agents

Năm agent hợp nhất, mỗi agent gọi domain skill trước khi bắt đầu làm việc.

| Agent | Model | Vai trò | Gọi skill |
|-------|-------|---------|----------|
| `planner` | Opus | Quản trị backlog, sprint planning, quyết định kiến trúc, ADR | skill `planning` |
| `builder` | Sonnet | Toàn bộ application code: frontend, backend, database, mobile | skill `frontend` / `backend` / `database` / `mobile` theo task |
| `designer` | Sonnet | User flow, design system, landing copy, SEO strategy | skill `design` / `content` theo task |
| `quality` | Sonnet | E2E test, test strategy, user guide, docs sau feature | skill `quality` / `docs` theo task |
| `infra` | Sonnet | CI/CD workflow, Dockerfile, cấu hình container | skill `cicd` / `docker` theo task |

---

## Domain Skills

Mười một skill mã hóa domain craft, có thể gọi trong mọi session sau khi plugin được cài.

| Skill | Nội dung bao phủ |
|-------|------------------|
| `planning` | ICE scoring, dependency graph, sprint health signal, C4 model, architecture pattern, ADR format, NFR checklist |
| `frontend` | Quyết định Server vs. Client Component, state management, Core Web Vitals, component pattern, form handling |
| `backend` | DDD building block, nguyên tắc API design, OWASP security checklist, caching strategy, background job |
| `database` | Framework quyết định index, pattern zero-downtime migration, tối ưu query, transaction isolation |
| `mobile` | Quyết định Expo Managed vs. Bare, navigation architecture, hiệu năng JS thread, pattern theo nền tảng |
| `design` | Framework quyết định thiết kế, visual hierarchy, nguyên tắc cognitive load, asset discovery protocol |
| `content` | Framework AIDA/PAS/FAB, brand voice, keyword intent, on-page SEO checklist, JSON-LD template |
| `quality` | Test pyramid strategy, Playwright fixture, chống flaky test, accessibility testing, tối ưu CI |
| `docs` | Framework Diátaxis, kỷ luật súc tích, cấu trúc USER_GUIDE, changelog format |
| `cicd` | Pipeline design, security scanning, release automation, deployment strategy, reusable workflow |
| `docker` | Multi-stage build, BuildKit cache mount, security hardening, chuẩn docker-compose |

---

## Bên Trong Có Gì

```
├── CLAUDE.md                     # Chỉ dẫn chính cho Claude (tự load mỗi session)
├── PRD.md                        # Product Requirements Document — agent đọc, không tự sửa
├── TODO.md                       # Backlog đã ưu tiên — con người quản lý, agent tham chiếu
├── START_HERE.md                 # Onboarding protocol — bị xóa sau setup
├── .mcp.json                     # Cấu hình MCP server (sequential-thinking, context7)
│
├── .claude/
│   ├── .claude-plugin/
│   │   └── plugin.json           # Plugin manifest — giúp skill có thể cài
│   ├── agents/                   # 5 agent hợp nhất
│   │   ├── planner.md            # Backlog & architecture (Opus)
│   │   ├── builder.md            # Toàn bộ application code (Sonnet)
│   │   ├── designer.md           # UX & content (Sonnet)
│   │   ├── quality.md            # Testing & documentation (Sonnet)
│   │   └── infra.md              # CI/CD & containers (Sonnet)
│   ├── skills/                   # 11 domain skill (mỗi thư mục có SKILL.md)
│   │   ├── planning/             # Project management & architecture craft
│   │   ├── frontend/             # Pattern implement React/Next.js
│   │   ├── backend/              # Pattern API & business logic
│   │   ├── database/             # Pattern schema design & migration
│   │   ├── mobile/               # Pattern React Native & Expo
│   │   ├── design/               # UX design process & visual hierarchy
│   │   ├── content/              # Framework copywriting & SEO
│   │   ├── quality/              # Testing strategy & Playwright pattern
│   │   ├── docs/                 # Viết documentation (Diátaxis)
│   │   ├── cicd/                 # Pipeline design & release automation
│   │   └── docker/               # Container architecture & security
│   ├── commands/
│   │   ├── orchestrate.md        # /orchestrate — thực thi multi-agent task
│   │   ├── status.md             # /status — live project health card
│   │   ├── start.md              # /start — onboarding protocol
│   │   └── sync-template.md      # /sync-template — kéo .claude/ mới nhất từ upstream
│   ├── rules/                    # File-scoped rule — inject khi file khớp đang mở
│   │   ├── typescript.md         # *.ts, *.tsx — không any, strict null, explicit return
│   │   ├── migrations.md         # *.sql, migrations/** — reversible, naming convention
│   │   └── tests.md              # *.spec.ts, *.test.ts — POM, data-testid, không test.only
│   ├── settings.json             # Cấu hình lifecycle hook
│   └── templates/                # Template doc trống — sync từ upstream
│
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── .tasks/                       # File task chi tiết — mỗi TODO item một file
│
└── docs/                         # Được tạo trong onboarding từ .claude/templates/
    ├── user/USER_GUIDE.md
    ├── technical/
    │   ├── ARCHITECTURE.md
    │   ├── DESIGN_SYSTEM.md
    │   ├── API.md
    │   ├── DATABASE.md
    │   └── DECISIONS.md
    └── content/
        └── CONTENT_STRATEGY.md
```

---

## Quy Ước Chính

**Commit** — [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(auth): add OAuth2 login with Google
fix(api): handle null response from payment provider
```

**Branch**:
```
feature/<ticket-id>-short-description
fix/<ticket-id>-short-description
```

**PRD là read-only** — `PRD.md` được bảo vệ bằng cơ chế ba lớp: warning block, rule trong CLAUDE.md, và system prompt của agent. Agent sẽ từ chối chỉnh sửa nếu không có chỉ thị rõ ràng từ con người.

**Documentation luôn cập nhật** — Agent phải cập nhật file `docs/` liên quan trước khi đánh dấu bất kỳ implementation task nào là hoàn tất.

**Convention là bắt buộc, không phải gợi ý** — Hook chạy ở cấp tool-call: `guard-destructive.sh` chặn command nguy hiểm trước khi chạy; `format-on-write.sh` chạy formatter của dự án mỗi lần lưu. File-scoped rule trong `.claude/rules/` chỉ inject standard khi loại file phù hợp đang active.

---

## Nguyên Tắc Thiết Kế

- **Skill thay vì system prompt** — domain craft nằm trong skill có thể gọi, không bị nhúng trong agent definition; agent vẫn mỏng, kiến thức vẫn tái sử dụng được
- **Thiết kế trước khi code** — `planner` tạo spec và ADR; `builder` implement
- **Copy trước implementation** — `designer` định nghĩa page copy và keyword target trước khi `builder` xây marketing page
- **Quyền sở hữu tài liệu** — mỗi file `docs/` có owner agent rõ ràng; agent khác không ghi đè
- **ADR append-only** — quyết định kiến trúc không bị âm thầm sửa; ADR mới supersede ADR cũ
- **Test map với requirement** — `quality` viết test theo item FR-XXX trong PRD, không theo chi tiết implementation
- **Hook thay vì chỉ dẫn** — chặn command phá hoại, auto-format, và completion check là shell script chạy 100% thời gian

---

## License

[MIT](LICENSE)
