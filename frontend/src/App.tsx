import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Bot,
  Check,
  Download,
  FileJson,
  Filter,
  FolderOpen,
  Gauge,
  History,
  Image,
  Keyboard,
  ListChecks,
  LogOut,
  Maximize2,
  MessageSquareText,
  Pause,
  Play,
  Plus,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Undo2,
  X,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import { api, clearAuthToken, setAuthToken } from "./api";
import { AIConfig, AIRangeFilter, AITask, AITaskResult, AuthUser, ConversationTurn, ExportMode, PageKey, Project, PromptTemplate, ProviderPreset, ReviewQueueFilter, ReviewStatus, Sample, Stats } from "./types";
import katex from "katex";
import "katex/dist/katex.min.css";

const statusText: Record<ReviewStatus, string> = { PASS: "通过", FAIL: "删除", SKIP: "通过", UNREVIEWED: "未审" };
const aiDecisionText: Record<string, string> = { PASS: "保留", FAIL: "删除", PENDING: "待审" };
const reviewQueueFilterText: Record<ReviewQueueFilter, string> = { ALL: "全部", MERGED_PASS: "审核通过", MERGED_FAIL: "审核不通过", MERGED_PENDING: "未审" };
const aiRangeText: Record<AIRangeFilter, string> = { HUMAN_UNREVIEWED: "人工未审且 AI 未审", AI_PENDING: "AI 未审", ALL: "全部样本" };
const exportModeText: Record<ExportMode, string> = { human_pass: "人工通过", ai_pass: "AI 保留", merged_pass: "合并导出" };
const visibleExportModes: ExportMode[] = ["merged_pass"];
const REVIEW_QUEUE_LIMIT = 10000;
const PROMPT_SELECTION_STORAGE_KEY = "qa-review-selected-prompts";
const DEFAULT_PROMPT_NAME = "默认审核";
const DEFAULT_AI_PROMPT = `你是问答数据集质量审核员。请判断样本是否应该保留。

审核标准：
1. 问题清晰、可回答，答案直接回应问题。
2. 答案事实一致、逻辑完整，没有明显幻觉、乱码、空答、重复或无关内容。
3. 多轮对话要检查上下文是否连贯，角色是否清楚。
4. 图文问答要检查答案是否依赖并匹配图片信息。
5. 只给可供人工复核的简短理由，不输出思维链。

样本：
问题：{{question}}
答案：{{answer}}
多轮对话：{{conversation}}
图片信息：{{image}}
其他字段：{{metadata}}

只输出 JSON，不要 Markdown：
{"pass": true/false, "score": 0-100, "reason": "一句话说明保留或删除原因"}`;
const emptyConfig: AIConfig = {
  provider_id: "custom",
  name: "默认配置",
  protocol: "openai-compatible",
  base_url: "",
  model: "",
  api_key: "",
  proxy_url: "",
  temperature: 0.1,
  max_tokens: 1200,
  timeout: 60
};
type PromptSelectionSetter = (value: number | null | ((current: number | null) => number | null)) => void;

function matchesReviewQueueFilter(sample: Sample, filter: ReviewQueueFilter) {
  if (filter === "ALL") return true;
  if (filter === "MERGED_PASS") return sample.review === "PASS" || sample.review === "SKIP" || (sample.review === "UNREVIEWED" && sample.ai === "PASS");
  if (filter === "MERGED_FAIL") return sample.review === "FAIL" || (sample.review === "UNREVIEWED" && sample.ai === "FAIL");
  if (filter === "MERGED_PENDING") return sample.review === "UNREVIEWED" && sample.ai === "PENDING";
  return true;
}

export default function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [page, setPage] = useState<PageKey>("ai");
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState("");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [sampleTotal, setSampleTotal] = useState(0);
  const [activeSample, setActiveSample] = useState(0);
  const [filter, setFilter] = useState<ReviewQueueFilter>("ALL");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [providers, setProviders] = useState<ProviderPreset[]>([]);
  const [selectedPromptByProject, setSelectedPromptByProject] = useState<Record<string, number>>(() => {
    try {
      const saved = window.localStorage.getItem(PROMPT_SELECTION_STORAGE_KEY);
      const parsed = saved ? JSON.parse(saved) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  });

  const project = projects.find((item) => item.id === activeProject) ?? projects[0];
  const projectId = project?.id;
  const sample = samples[activeSample];
  const selectedPromptId = projectId ? selectedPromptByProject[projectId] ?? null : null;

  useEffect(() => {
    api.me().then(setAuthUser).catch(() => clearAuthToken()).finally(() => setAuthChecking(false));
  }, []);

  const setSelectedPromptId = useCallback<PromptSelectionSetter>((value) => {
    if (!projectId) return;
    setSelectedPromptByProject((current) => {
      const currentValue = current[projectId] ?? null;
      const nextValue = typeof value === "function" ? value(currentValue) : value;
      if (nextValue === currentValue) return current;
      const next = { ...current };
      if (nextValue == null) {
        delete next[projectId];
      } else {
        next[projectId] = nextValue;
      }
      try {
        window.localStorage.setItem(PROMPT_SELECTION_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // localStorage can be unavailable in locked-down browser contexts; keep the in-memory selection.
      }
      return next;
    });
  }, [projectId]);

  const loadProjects = useCallback(async () => {
    if (!authUser) return;
    try {
      const items = await api.projects();
      setProjects(items);
      setActiveProject((current) => items.some((item) => item.id === current) ? current : items[0]?.id || "");
      if (!items.length) setPage((current) => current === "settings" ? current : "import");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "后端连接失败");
    }
  }, [authUser]);

  const loadSamples = useCallback(async (nextIndex = 0) => {
    if (!projectId) return;
    try {
      const result = await api.samples(projectId, "ALL", query, REVIEW_QUEUE_LIMIT, 0);
      const visibleSamples = result.items.filter((item) => matchesReviewQueueFilter(item, filter));
      setSamples(visibleSamples);
      setSampleTotal(visibleSamples.length);
      setActiveSample(Math.min(Math.max(nextIndex, 0), Math.max(visibleSamples.length - 1, 0)));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "样本加载失败");
    }
  }, [filter, projectId, query]);

  useEffect(() => {
    if (!authUser) return;
    loadProjects();
    api.providers().then(setProviders).catch(() => setProviders([]));
  }, [authUser, loadProjects]);

  useEffect(() => {
    loadSamples(0);
  }, [loadSamples]);

  const review = async (status: ReviewStatus) => {
    if (!project || !sample || saving) return;
    const nextIndex = filter === "ALL" ? activeSample + 1 : activeSample;
    setSaving(true);
    try {
      await api.review(project.id, sample.id, { status });
      await loadProjects();
      await loadSamples(nextIndex);
    } finally {
      setSaving(false);
    }
  };

  const undo = async () => {
    if (!project) return;
    await api.undo(project.id);
    await loadProjects();
    await loadSamples(activeSample);
  };

  const move = (delta: number) => {
    setActiveSample((index) => Math.min(Math.max(index + delta, 0), Math.max(samples.length - 1, 0)));
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return;
      if (event.ctrlKey && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
        return;
      }
      if (event.key.toLowerCase() === "a") review("PASS");
      if (event.key.toLowerCase() === "d") review("FAIL");
      if (event.key.toLowerCase() === "s") review("PASS");
      if (event.key === "ArrowRight" || event.key === " ") move(1);
      if (event.key === "ArrowLeft") move(-1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const logout = () => {
    clearAuthToken();
    setAuthUser(null);
    setProjects([]);
    setActiveProject("");
    setSamples([]);
    setPage("ai");
  };

  if (authChecking) {
    return <main className="authShell"><section className="authPanel"><div className="brandMark">QA</div><h1>正在连接</h1></section></main>;
  }
  if (!authUser) return <LoginPage onLogin={setAuthUser} />;

  return (
    <main className="shell">
      <aside className="rail" aria-label="主导航">
        <div className="brand">
          <div className="brandMark">QA</div>
          <div>
            <strong>问答审核</strong>
            <span>Workbench</span>
          </div>
        </div>
        <nav className="nav">
          <NavItem icon={<FolderOpen />} label="项目" active={page === "projects"} onClick={() => setPage("projects")} />
          <NavItem icon={<Plus />} label="导入" active={page === "import"} onClick={() => setPage("import")} />
          <NavItem icon={<Bot />} label="AI审核模式" active={page === "ai"} onClick={() => setPage("ai")} />
          <NavItem icon={<ListChecks />} label="人工复审核" active={page === "review"} onClick={() => { setFilter("ALL"); setPage("review"); }} />
          <NavItem icon={<MessageSquareText />} label="Prompt" active={page === "prompts"} onClick={() => setPage("prompts")} />
          <NavItem icon={<BarChart3 />} label="统计" active={page === "stats"} onClick={() => setPage("stats")} />
          <NavItem icon={<Download />} label="导出" active={page === "export"} onClick={() => setPage("export")} />
          <NavItem icon={<Settings />} label="设置" active={page === "settings"} onClick={() => setPage("settings")} />
        </nav>
        <div className="railFooter">
          <span className={error ? "lamp error" : "lamp on"} />
          <span>{authUser.username || authUser.email}</span>
          <button className="iconButton" onClick={logout} title="退出登录"><LogOut size={16} /></button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <h1>{project?.name ?? "问答审核"}</h1>
          <div className="topActions">
            <label className="searchBox">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索" />
            </label>
            <button className="iconButton" onClick={() => setPage("settings")} title="设置">
              <SlidersHorizontal size={18} />
            </button>
          </div>
        </header>

        {error && <div className="errorBanner">{error}</div>}
        {page === "projects" && <ProjectsPage projects={projects} activeProject={activeProject} setActiveProject={setActiveProject} setPage={setPage} refresh={loadProjects} />}
        {page === "import" && <ImportPage setActiveProject={setActiveProject} setPage={setPage} refresh={loadProjects} />}
        {page === "review" && project && (
          sample ? (
            <ReviewPage
              project={project}
              samples={samples}
              total={sampleTotal}
              sample={sample}
              activeSample={activeSample}
              setActiveSample={setActiveSample}
              filter={filter}
              setFilter={setFilter}
              review={review}
              move={move}
              undo={undo}
              saving={saving}
              refresh={async () => {
                await Promise.all([loadProjects(), loadSamples(activeSample)]);
              }}
            />
          ) : (
            <ReviewEmptyState
              filter={filter}
              setFilter={setFilter}
              setPage={setPage}
              refresh={async () => {
                await Promise.all([loadProjects(), loadSamples(0)]);
              }}
            />
          )
        )}
        {page === "ai" && project && <AIPage project={project} providers={providers} selectedPromptId={selectedPromptId} setSelectedPromptId={setSelectedPromptId} />}
        {page === "prompts" && project && <PromptPage project={project} selectedPromptId={selectedPromptId} setSelectedPromptId={setSelectedPromptId} />}
        {page === "stats" && project && <StatsPage project={project} />}
        {page === "export" && project && <ExportPage project={project} />}
        {page === "settings" && <SettingsPage providers={providers} />}
      </section>
    </main>
  );
}

function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const submit = async () => {
    if (mode === "register" && password !== confirmPassword) {
      setMessage("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const session = mode === "register"
        ? await api.register(account, password)
        : await api.login(account, password);
      setAuthToken(session.access_token);
      onLogin(session.user);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : mode === "register" ? "注册失败" : "登录失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="authShell">
      <section className="authPanel">
        <div className="brandMark">QA</div>
        <h1>问答审核</h1>
        <div className="authTabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setMessage(""); }}>登录</button>
          <button className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setMessage(""); }}>注册</button>
        </div>
        <label>账号<input autoFocus value={account} onChange={(event) => setAccount(event.target.value)} placeholder="请输入账号" /></label>
        <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="至少 6 位" /></label>
        {mode === "register" && <label>确认密码<input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="再次输入密码" /></label>}
        <div className="rowActions">
          <button className="primary" disabled={busy || !account || !password || (mode === "register" && !confirmPassword)} onClick={submit}>
            {busy ? "处理中" : mode === "register" ? "注册并进入" : "登录"}
          </button>
        </div>
        {message && <p className="formMessage">{message}</p>}
      </section>
    </main>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={active ? "navItem active" : "navItem"} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function ProjectsPage(props: { projects: Project[]; activeProject: string; setActiveProject: (id: string) => void; setPage: (page: PageKey) => void; refresh: () => Promise<void> }) {
  const { projects, activeProject, setActiveProject, setPage, refresh } = props;
  const [deletingProject, setDeletingProject] = useState("");

  const removeProject = async (project: Project) => {
    if (!window.confirm(`删除项目「${project.name}」？`)) return;
    setDeletingProject(project.id);
    try {
      await api.deleteProject(project.id);
      if (project.id === activeProject) {
        const nextProject = projects.find((item) => item.id !== project.id);
        setActiveProject(nextProject?.id || "");
      }
      await refresh();
    } finally {
      setDeletingProject("");
    }
  };

  return (
    <div className="projectGrid">
      {projects.map((project) => (
        <article className={project.id === activeProject ? "projectCard selected" : "projectCard"} key={project.id}>
          <div className="projectHead">
            <div>
              <h2>{project.name}</h2>
              <p>{project.type}</p>
            </div>
            <span className="chip">{project.total ? Math.round((project.reviewed / project.total) * 100) : 0}%</span>
          </div>
          <Progress value={project.total ? (project.reviewed / project.total) * 100 : 0} />
          <dl className="metricRow">
            <div><dt>总量</dt><dd>{project.total.toLocaleString()}</dd></div>
            <div><dt>人工</dt><dd>{project.reviewed.toLocaleString()}</dd></div>
            <div><dt>AI审核</dt><dd>{project.ai_reviewed.toLocaleString()}</dd></div>
          </dl>
          <p className="pathLine">{project.source_path}</p>
          <div className="rowActions">
            <button onClick={() => { setActiveProject(project.id); setPage("ai"); }}>打开</button>
            <button className="dangerText" disabled={deletingProject === project.id} onClick={() => removeProject(project)}><Trash2 />删除</button>
          </div>
        </article>
      ))}
      <button className="newProject" onClick={() => setPage("import")}>
        <Plus />
        <span>新建项目</span>
      </button>
    </div>
  );
}

function ImportPage({ setActiveProject, setPage, refresh }: { setActiveProject: (id: string) => void; setPage: (page: PageKey) => void; refresh: () => void }) {
  const [form, setForm] = useState({ name: "新建审核项目", dataset_type: "图片问答", source_path: "", media_path: "" });
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [mediaFiles, setMediaFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [inspect, setInspect] = useState<any>(null);
  const [message, setMessage] = useState("");
  const isImageDataset = form.dataset_type === "图片问答";

  const update = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const create = async () => {
    if (!datasetFile) {
      setMessage("请先选择数据文件");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const project = await api.createProjectUpload({ name: form.name, dataset_type: form.dataset_type, datasetFile, mediaFiles: isImageDataset ? mediaFiles : [] });
      setActiveProject(project.id);
      await refresh();
      setPage("ai");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "创建项目失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="importFlow">
      <section className="wizardPanel">
        <h2>新建项目</h2>
        <div className="fieldGrid">
          <label>名称<input value={form.name} onChange={(event) => update("name", event.target.value)} /></label>
          <label>类型<select value={form.dataset_type} onChange={(event) => { update("dataset_type", event.target.value); if (event.target.value !== "图片问答") setMediaFiles([]); }}><option>单轮问答</option><option>多轮对话</option><option>图片问答</option></select></label>
          <PathField label="数据文件" value={form.source_path} onChange={(value) => update("source_path", value)} onFiles={(files) => setDatasetFile(files[0] ?? null)} picker="file" accept=".json,.jsonl,.csv" />
          {isImageDataset && <PathField label="媒体资源" value={form.media_path} onChange={(value) => update("media_path", value)} onFiles={setMediaFiles} picker="both" accept=".zip,.jpg,.jpeg,.png,.webp" />}
        </div>
        <div className="rowActions">
          <button disabled={!datasetFile || busy} onClick={async () => {
            if (!datasetFile) return;
            setMessage("");
            try {
              setInspect(await api.inspectUpload(datasetFile));
            } catch (err) {
              setMessage(err instanceof Error ? err.message : "字段识别失败");
            }
          }}>识别字段</button>
          <button className="primary" disabled={busy || !datasetFile} onClick={create}>{busy ? "创建中" : "创建项目"}</button>
        </div>
        {message && <p className="formMessage">{message}</p>}
      </section>
      <section className="inspectionPanel">
        <h2>字段识别</h2>
        <Step label="类型" value={inspect?.dataset_type ?? "-"} score={String(inspect?.total ?? "-")} done={Boolean(inspect)} />
        <Step label="问题" value={inspect?.field_map?.question ?? "-"} score={String(inspect?.confidence?.question ?? "-")} done={Boolean(inspect?.field_map?.question)} />
        <Step label="答案" value={inspect?.field_map?.answer ?? "-"} score={String(inspect?.confidence?.answer ?? "-")} done={Boolean(inspect?.field_map?.answer)} />
        <Step label="图片" value={inspect?.field_map?.image ?? "-"} score={String(inspect?.confidence?.image ?? "-")} done={Boolean(inspect?.field_map?.image)} />
        <Step label="多轮" value={inspect?.field_map?.conversation ?? "-"} score={String(inspect?.confidence?.conversation ?? "-")} done={Boolean(inspect?.field_map?.conversation)} />
      </section>
    </div>
  );
}

function PathField(props: { label: string; value: string; onChange: (value: string) => void; onFiles?: (files: File[]) => void; picker: "file" | "folder" | "both"; accept?: string }) {
  const { label, value, onChange, onFiles, picker, accept } = props;
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    folderRef.current?.setAttribute("webkitdirectory", "");
    folderRef.current?.setAttribute("directory", "");
  }, []);

  const chooseFolder = async () => {
    folderRef.current?.click();
  };

  const chooseFile = () => fileRef.current?.click();
  const fileSelected = (files: FileList | null) => {
    const selected = Array.from(files ?? []);
    const first = selected[0];
    if (!first) return;
    const relative = first.webkitRelativePath;
    onChange(relative || first.name);
    onFiles?.(selected);
  };

  return (
    <label className="pathField">
      {label}
      <span className="pathInput">
        <input value={value} readOnly />
        {(picker === "file" || picker === "both") && (
          <button type="button" className="iconButton" onClick={chooseFile} title="选择文件">
            <FileJson size={17} />
          </button>
        )}
        {(picker === "folder" || picker === "both") && (
          <button type="button" className="iconButton" onClick={chooseFolder} title="选择文件夹">
            <FolderOpen size={17} />
          </button>
        )}
      </span>
      <input ref={fileRef} className="hiddenPicker" type="file" accept={accept} multiple={picker === "both"} onChange={(event) => fileSelected(event.currentTarget.files)} />
      <input ref={folderRef} className="hiddenPicker" type="file" multiple onChange={(event) => fileSelected(event.currentTarget.files)} />
    </label>
  );
}

function ReviewPage(props: {
  project: Project;
  samples: Sample[];
  total: number;
  sample: Sample;
  activeSample: number;
  setActiveSample: (index: number) => void;
  filter: ReviewQueueFilter;
  setFilter: (status: ReviewQueueFilter) => void;
  review: (status: ReviewStatus) => void;
  move: (delta: number) => void;
  undo: () => void;
  saving: boolean;
  refresh: () => Promise<void>;
}) {
  const { project, samples, total, sample, activeSample, setActiveSample, filter, setFilter, review, move, undo, saving, refresh } = props;
  const media = sample.media[0];
  const answerParts = splitReasoning(sample.edited_answer ?? sample.answer);
  const isImageProject = project.type === "图片问答";
  const conversation = sample.conversation ?? [];
  const isConversationProject = project.type === "多轮对话" || conversation.length > 0;
  return (
    <div className="reviewConsole">
      <section className={isImageProject ? "sampleStage" : "sampleStage textOnly"}>
        <div className="consoleHeader">
          <div>
            <span className="tiny">样本</span>
            <h2>{sample.external_id}</h2>
          </div>
          <div className="statusPair">
            <AiBadge status={sample.ai} />
            <StatusBadge status={sample.review} />
          </div>
        </div>
        {isImageProject && <MediaPreview projectId={project.id} media={media} />}
        {isConversationProject ? (
          <ConversationBlock turns={conversation} fallback={sample.edited_question ?? sample.question} />
        ) : (
          <>
            <TextBlock label="问题" value={sample.edited_question ?? sample.question} />
            {answerParts.reasoning && <TextBlock label="思维链" value={answerParts.reasoning} tone="reasoning" />}
            {answerParts.answer && <TextBlock label="答案" value={answerParts.answer} tone="answer" />}
          </>
        )}
        <div className="tagLine">{sample.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
        <div className="reviewActions">
          <button className="pass" disabled={saving} onClick={() => review("PASS")}><Check />确认通过 <kbd>A / S</kbd></button>
          <button className="fail" disabled={saving} onClick={() => review("FAIL")}><Trash2 />确认删除 <kbd>D</kbd></button>
          <button disabled={saving} onClick={undo}><Undo2 />撤销 <kbd>Ctrl Z</kbd></button>
        </div>
      </section>
      <aside className="sideStack">
        <section className="instrument">
          <h3><Gauge size={17} />复核仪表</h3>
          <Progress value={project.total ? (project.reviewed / project.total) * 100 : 0} />
          <dl className="denseMetrics">
            <div><dt>位置</dt><dd>{activeSample + 1} / {total}</dd></div>
            <div><dt>人工复核</dt><dd>{project.total ? Math.round((project.reviewed / project.total) * 100) : 0}%</dd></div>
            <div><dt>AI分</dt><dd>{sample.ai_score || "-"} / 100</dd></div>
            <div><dt>AI判断</dt><dd><AiBadge status={sample.ai} /></dd></div>
          </dl>
        </section>
        <section className="instrument queueInstrument">
          <div className="instrumentTitle">
            <h3><Filter size={17} />队列</h3>
            <button className="iconButton" onClick={refresh} title="刷新队列"><RefreshCcw size={16} /></button>
          </div>
          <div className="segmented">
            {(["ALL", "MERGED_PASS", "MERGED_FAIL", "MERGED_PENDING"] as const).map((item) => (
              <button className={filter === item ? "selected" : ""} key={item} onClick={() => setFilter(item)}>{reviewQueueFilterText[item]}</button>
            ))}
          </div>
          <div className="queue">
            {samples.map((item, index) => (
              <button className={item.id === sample.id ? "queueItem active" : "queueItem"} key={item.id} onClick={() => setActiveSample(index)}>
                <strong>{item.external_id}</strong>
                <span className="queuePos">#{index + 1}</span>
                <span className="queueBadges">
                  <AiBadge status={item.ai} compact />
                  <StatusBadge status={item.review} compact />
                </span>
              </button>
            ))}
          </div>
          <div className="pager">
            <button onClick={() => move(-1)}><ArrowLeft />上一条</button>
            <button onClick={() => move(1)}>下一条<ArrowRight /></button>
          </div>
        </section>
        <section className="instrument">
          <h3><History size={17} />备注</h3>
          <p className="muted">{sample.note || sample.ai_reason || "无"}</p>
        </section>
      </aside>
    </div>
  );
}

function ReviewEmptyState({
  filter,
  setFilter,
  setPage,
  refresh
}: {
  filter: ReviewQueueFilter;
  setFilter: (status: ReviewQueueFilter) => void;
  setPage: (page: PageKey) => void;
  refresh: () => Promise<void>;
}) {
  return (
    <section className="emptyReview panel">
      <div className="emptyReviewIcon"><Filter size={24} /></div>
      <h2>当前筛选没有条目</h2>
      <p>{filter === "ALL" ? "这个项目还没有可复核的样本。" : `${reviewQueueFilterText[filter]} 里暂时没有条目。`}</p>
      <div className="rowActions">
        <button className="primary" onClick={() => setFilter("ALL")}>查看全部</button>
        <button onClick={refresh}><RefreshCcw />刷新</button>
        <button onClick={() => setPage("ai")}><Bot />去 AI 审核</button>
      </div>
    </section>
  );
}

function AIPage({
  project,
  providers,
  selectedPromptId,
  setSelectedPromptId
}: {
  project: Project;
  providers: ProviderPreset[];
  selectedPromptId: number | null;
  setSelectedPromptId: PromptSelectionSetter;
}) {
  const [config, setConfig] = useState<AIConfig>(emptyConfig);
  const [configs, setConfigs] = useState<AIConfig[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [tasks, setTasks] = useState<AITask[]>([]);
  const [results, setResults] = useState<AITaskResult[]>([]);
  const [message, setMessage] = useState("");
  const [testPrompt, setTestPrompt] = useState("请回复：模型连接测试成功。");
  const [testResult, setTestResult] = useState<{ ok: boolean; content: string; elapsed_ms?: number; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [aiRange, setAiRange] = useState<AIRangeFilter>("HUMAN_UNREVIEWED");
  const selectedConfig = configs[0];
  const selectedPrompt = prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0];

  const load = useCallback(async () => {
    const [nextConfigs, nextPrompts, nextTasks] = await Promise.all([api.configs(project.id), api.prompts(project.id), api.tasks(project.id)]);
    setConfigs(nextConfigs);
    if (nextConfigs[0]) {
      setConfig((current) => current.base_url || current.model ? current : { ...nextConfigs[0], proxy_url: nextConfigs[0].proxy_url || current.proxy_url });
    }
    setPrompts(nextPrompts);
    setSelectedPromptId((current) => current && nextPrompts.some((prompt) => prompt.id === current) ? current : nextPrompts[0]?.id ?? null);
    setTasks(nextTasks);
    const activeTask = nextTasks[0];
    if (activeTask) {
      try {
        setResults(await api.taskResults(project.id, activeTask.id, 100));
      } catch {
        setResults([]);
      }
    } else {
      setResults([]);
    }
  }, [project.id, setSelectedPromptId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (config.proxy_url) return;
    api.localProxy()
      .then((result) => {
        if (!result.proxy_url) return;
        setConfig((current) => current.proxy_url ? current : { ...current, proxy_url: result.proxy_url });
      })
      .catch(() => undefined);
  }, [config.proxy_url]);

  useEffect(() => {
    if (!tasks.some((item) => item.status === "queued" || item.status === "running")) return;
    const timer = window.setInterval(load, 2500);
    return () => window.clearInterval(timer);
  }, [load, tasks]);

  const chooseProvider = (id: string) => {
    const preset = providers.find((item) => item.id === id);
    if (!preset) return;
    setConfig((current) => ({ ...current, provider_id: preset.id, name: preset.name, protocol: preset.protocol, base_url: preset.base_url, model: preset.default_model }));
  };

  const save = async () => {
    try {
      const saved = await api.saveConfig(project.id, config);
      setConfigs([saved]);
      setMessage("已保存");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存失败");
    }
  };

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    setMessage("测试中");
    try {
      const result = await api.chatTest(project.id, { ...config, prompt: testPrompt });
      setTestResult({ ok: true, content: result.content || "模型返回为空。", elapsed_ms: result.elapsed_ms });
      setMessage("测试完成");
    } catch (err) {
      setTestResult({ ok: false, content: "", error: err instanceof Error ? err.message : "模型测试失败" });
      setMessage("测试失败");
    } finally {
      setTesting(false);
    }
  };

  const start = async () => {
    setStarting(true);
    setMessage("正在启动");
    try {
      const currentConfigReady = Boolean(
        config.base_url.trim() &&
        config.model.trim() &&
        (config.api_key.trim() || config.base_url.startsWith("http://127.0.0.1") || config.base_url.startsWith("http://localhost"))
      );
      const runConfig = currentConfigReady ? await api.saveConfig(project.id, config) : selectedConfig;
      if (!runConfig?.id) {
        setMessage("请先填写模型配置");
        return;
      }
      let runPrompt = selectedPrompt;
      if (!runPrompt) {
        runPrompt = await api.savePrompt(project.id, { name: DEFAULT_PROMPT_NAME, content: DEFAULT_AI_PROMPT });
      }
      await api.startTask(project.id, { config_id: runConfig.id, prompt_id: runPrompt.id, range_filter: aiRange });
      setConfigs([runConfig]);
      setPrompts((current) => current.some((item) => item.id === runPrompt.id) ? current.map((item) => item.id === runPrompt.id ? runPrompt : item) : [runPrompt, ...current]);
      setSelectedPromptId(runPrompt.id);
      setResults([]);
      setMessage("任务已启动");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "启动失败");
    } finally {
      setStarting(false);
    }
  };

  const task = tasks[0];
  const progress = task?.total ? (task.completed / task.total) * 100 : 0;
  const activePrompt = selectedPrompt ?? prompts.find((prompt) => prompt.id === task?.prompt_id);
  const promptName = activePrompt?.name ?? DEFAULT_PROMPT_NAME;
  const promptContent = activePrompt?.content ?? DEFAULT_AI_PROMPT;
  const refreshTaskQueue = async () => {
    if (!task) {
      await load();
      return;
    }
    try {
      await api.taskAction(project.id, task.id, "refresh");
      setMessage("队列已刷新");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "刷新失败");
    }
  };
  return (
    <div className="twoColumn aiPage">
      <section className="panel">
        <h2>AI审核配置</h2>
        <div className="fieldGrid">
          <label>服务商<select value={config.provider_id} onChange={(event) => chooseProvider(event.target.value)}>{providers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>协议<select value={config.protocol} onChange={(event) => setConfig({ ...config, protocol: event.target.value })}><option value="openai-compatible">OpenAI Compatible</option><option value="anthropic-messages">Anthropic Messages</option><option value="gemini-generate-content">Gemini generateContent</option></select></label>
          <label>Base URL<input value={config.base_url} onChange={(event) => setConfig({ ...config, base_url: event.target.value })} /></label>
          <label>模型<input value={config.model} onChange={(event) => setConfig({ ...config, model: event.target.value })} /></label>
          <label>API Key<input type="password" value={config.api_key} onChange={(event) => setConfig({ ...config, api_key: event.target.value })} /></label>
          <label>代理地址<input value={config.proxy_url} onChange={(event) => setConfig({ ...config, proxy_url: event.target.value })} /></label>
          <label>Temperature<input value={config.temperature} onChange={(event) => setConfig({ ...config, temperature: Number(event.target.value) || 0 })} /></label>
          <label>Prompt<select value={selectedPrompt?.id ?? ""} onChange={(event) => setSelectedPromptId(event.target.value ? Number(event.target.value) : null)}>{prompts.map((prompt) => <option key={prompt.id} value={prompt.id}>{prompt.name}</option>)}</select></label>
          <label>审核范围<select value={aiRange} onChange={(event) => setAiRange(event.target.value as AIRangeFilter)}>{(Object.keys(aiRangeText) as AIRangeFilter[]).map((item) => <option key={item} value={item}>{aiRangeText[item]}</option>)}</select></label>
        </div>
        <div className="chatTestBox">
          <label>对话测试<textarea value={testPrompt} onChange={(event) => setTestPrompt(event.target.value)} /></label>
          {testResult && (
            <div className={testResult.ok ? "chatResult" : "chatResult error"}>
              <strong>{testResult.ok ? `模型返回 · ${testResult.elapsed_ms}ms` : "测试失败"}</strong>
              <p>{testResult.ok ? testResult.content : testResult.error}</p>
            </div>
          )}
        </div>
        <div className="rowActions">
          <button onClick={test} disabled={testing}>{testing ? "测试中" : "对话测试"}</button>
          <button onClick={save}>保存</button>
          <button className="primary" onClick={start} disabled={starting}><Play />{starting ? "启动中" : "启动"}</button>
        </div>
        {message && <p className="terminalLine">{message}</p>}
      </section>
      <section className="panel">
        <h2>任务</h2>
        <div className="meterLarge"><Progress value={progress} /><strong>{Math.round(progress)}%</strong></div>
        {task ? (
          <>
            <Step label="状态" value={task.status} score={`${task.completed}/${task.total}`} done={task.status === "completed"} />
            <Step label="范围" value={aiRangeText[task.range_filter as AIRangeFilter] ?? task.range_filter} score="" done={false} />
            <div className="rowActions">
              <button onClick={() => api.taskAction(project.id, task.id, "pause").then(load)}><Pause />暂停</button>
              <button onClick={refreshTaskQueue}><RefreshCcw />刷新队列</button>
              <button onClick={() => api.taskAction(project.id, task.id, "resume").then(load)}><RefreshCcw />继续</button>
              <button className="dangerText" onClick={() => api.taskAction(project.id, task.id, "stop").then(load)}><X />停止</button>
            </div>
          </>
        ) : <p className="muted">无任务</p>}
      </section>
      <section className="panel aiMonitor">
        <h2>AI 实时审核</h2>
        <div className="monitorGrid">
          <div className="promptPreview">
            <div className="monitorHeader">
              <span>当前 Prompt</span>
              <strong>{promptName}</strong>
            </div>
            <pre>{promptContent}</pre>
          </div>
          <div className="resultFeed">
            <div className="monitorHeader">
              <span>实时结果</span>
              <strong>{task ? `${task.completed}/${task.total}` : "0/0"}</strong>
            </div>
            {results.length ? results.map((item) => (
              <article className="resultRow" key={item.sample_id}>
                <div className="resultTopline">
                  <strong>{item.external_id}</strong>
                  <span className={`resultDecision ${item.ai_status.toLowerCase()}`}>{aiDecisionText[item.ai_status] ?? item.ai_status}</span>
                  <span>{Math.round(item.ai_score || 0)}分</span>
                </div>
                <p>{item.ai_reason || "无理由"}</p>
                <small>{item.question}</small>
              </article>
            )) : <p className="muted">暂无结果</p>}
          </div>
        </div>
      </section>
    </div>
  );
}

function PromptPage({
  project,
  selectedPromptId,
  setSelectedPromptId
}: {
  project: Project;
  selectedPromptId: number | null;
  setSelectedPromptId: PromptSelectionSetter;
}) {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [name, setName] = useState(DEFAULT_PROMPT_NAME);
  const [content, setContent] = useState(DEFAULT_AI_PROMPT);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const nextPrompts = await api.prompts(project.id);
    setPrompts(nextPrompts);
    setSelectedPromptId((current) => current && nextPrompts.some((prompt) => prompt.id === current) ? current : nextPrompts[0]?.id ?? null);
    return nextPrompts;
  }, [project.id, setSelectedPromptId]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const activePrompt = prompts.find((prompt) => prompt.id === selectedPromptId);
    if (!activePrompt) return;
    setName(activePrompt.name);
    setContent(activePrompt.content);
  }, [prompts, selectedPromptId]);

  const savePrompt = async () => {
    setSaving(true);
    try {
      const payload = { name: name.trim() || DEFAULT_PROMPT_NAME, content };
      const activePrompt = prompts.find((prompt) => prompt.id === selectedPromptId);
      const saved = activePrompt
        ? await api.updatePrompt(project.id, activePrompt.id, payload)
        : await api.savePrompt(project.id, payload);
      const nextPrompts = await load();
      setSelectedPromptId(saved.id);
      if (!nextPrompts.some((prompt) => prompt.id === saved.id)) {
        setPrompts((current) => [saved, ...current]);
      }
      setName(saved.name);
      setContent(saved.content);
    } finally {
      setSaving(false);
    }
  };

  const createPrompt = () => {
    setSelectedPromptId(null);
    setName(`${DEFAULT_PROMPT_NAME}${prompts.length + 1}`);
    setContent(DEFAULT_AI_PROMPT);
  };

  return (
    <div className="twoColumn">
      <section className="panel">
        <h2>Prompt</h2>
        <label>名称<input value={name} onChange={(event) => setName(event.target.value)} /></label>
        <textarea value={content} onChange={(event) => setContent(event.target.value)} />
        <div className="rowActions">
          <button onClick={createPrompt}>新建</button>
          <button className="primary" disabled={saving} onClick={savePrompt}>{saving ? "保存中" : "保存"}</button>
        </div>
      </section>
      <section className="panel">
        <h2>模板</h2>
        {prompts.map((prompt) => (
          <button
            key={prompt.id}
            className={prompt.id === selectedPromptId ? "promptRow active" : "promptRow"}
            onClick={() => {
              setSelectedPromptId(prompt.id);
              setName(prompt.name);
              setContent(prompt.content);
            }}
          >
            {prompt.name}
          </button>
        ))}
      </section>
    </div>
  );
}

function StatsPage({ project }: { project: Project }) {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => { api.stats(project.id).then(setStats); }, [project.id]);
  const counts = stats?.review ?? { PASS: 0, FAIL: 0, SKIP: 0, UNREVIEWED: 0 };
  const total = stats?.total || 1;
  return (
    <div className="statsGrid">
      <section className="panel wide">
        <h2>统计</h2>
        <div className="barSet">
          {(Object.keys(counts) as ReviewStatus[]).map((key) => (
            <div className="barRow" key={key}>
              <span>{statusText[key]}</span>
              <div><i className={key.toLowerCase()} style={{ width: `${Math.max(8, (counts[key] / total) * 100)}%` }} /></div>
              <strong>{counts[key]}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>人机一致率</h2>
        <div className="agreement">{stats?.agreement ?? 0}%</div>
      </section>
    </div>
  );
}

function ExportPage({ project }: { project: Project }) {
  const [result, setResult] = useState<{ mode: ExportMode; filename: string; target: string; rows: number } | null>(null);
  const [exporting, setExporting] = useState<ExportMode | null>(null);

  const exportFile = async (mode: ExportMode) => {
    setExporting(mode);
    try {
      const file = await api.exportProject(project.id, mode);
      const rows = await countJsonlRows(file.blob);
      const picker = (window as any).showDirectoryPicker;
      if (typeof picker === "function") {
        const directory = await picker();
        const handle = await directory.getFileHandle(file.filename, { create: true });
        const writable = await handle.createWritable();
        await writable.write(file.blob);
        await writable.close();
        setResult({ mode, filename: file.filename, target: directory.name || "已选择文件夹", rows });
      } else {
        const url = URL.createObjectURL(file.blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = file.filename;
        link.click();
        URL.revokeObjectURL(url);
        setResult({ mode, filename: file.filename, target: "浏览器下载", rows });
      }
    } catch (err) {
      const cancelled = err instanceof DOMException && err.name === "AbortError";
      setResult({ mode, filename: cancelled ? "已取消" : err instanceof Error ? err.message : "导出失败", target: cancelled ? "未导出" : "失败", rows: 0 });
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="twoColumn">
      <section className="panel">
        <h2>导出</h2>
        <div className="exportActions">
          {visibleExportModes.map((mode) => (
            <button className={mode === "merged_pass" ? "primary" : ""} key={mode} onClick={() => exportFile(mode)} disabled={Boolean(exporting)}>
              <Download />{exporting === mode ? "导出中" : exportModeText[mode]}
            </button>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>结果</h2>
        {result ? <><p className="terminalLine">{exportModeText[result.mode]} · {result.target}</p><p className="terminalLine">{result.filename}</p><p className="terminalLine">rows: {result.rows}</p></> : <p className="muted">无</p>}
      </section>
    </div>
  );
}

async function countJsonlRows(blob: Blob) {
  const text = await blob.text();
  return text.split(/\r?\n/).filter(Boolean).length;
}

function SettingsPage({ providers }: { providers: ProviderPreset[] }) {
  return (
    <div className="settingsGrid">
      <section className="panel">
        <h2><Settings size={18} />存储</h2>
        <p className="shortcut"><span>项目文件</span><code>服务器托管</code></p>
        <p className="shortcut"><span>导出文件</span><code>浏览器下载</code></p>
      </section>
      <section className="panel">
        <h2><Keyboard size={18} />快捷键</h2>
        <Shortcut action="通过" keyName="A" />
        <Shortcut action="删除" keyName="D" />
        <Shortcut action="略过" keyName="S" />
        <Shortcut action="下一条" keyName="Space / →" />
        <Shortcut action="撤销" keyName="Ctrl + Z" />
      </section>
      <section className="panel">
        <h2><ShieldCheck size={18} />API 服务商</h2>
        {providers.map((item) => <p className="shortcut" key={item.id}><span>{item.name}</span><code>{item.protocol}</code></p>)}
      </section>
    </div>
  );
}

function splitReasoning(value: string) {
  const text = value || "";
  const thinkPattern = /<think\b[^>]*>([\s\S]*?)(?:<\/think>|$)/gi;
  const thinkMatches = [...text.matchAll(thinkPattern)];
  if (thinkMatches.length) {
    const reasoning = thinkMatches.map((match) => match[1].trim()).filter(Boolean).join("\n\n");
    const answer = cleanAnswerHeading(text.replace(thinkPattern, "").trim());
    return { reasoning, answer };
  }

  const reasoningMarker = /(?:^|\n)\s*(?:思维链|推理过程|思考过程|reasoning|chain of thought)\s*[:：]\s*/i;
  const answerMarker = /(?:^|\n)\s*(?:最终答案|答案|final answer|answer)\s*[:：]\s*/i;
  const reasoningMatch = reasoningMarker.exec(text);
  const answerMatch = answerMarker.exec(text);
  if (reasoningMatch && answerMatch && answerMatch.index > reasoningMatch.index) {
    const reasoningStart = reasoningMatch.index + reasoningMatch[0].length;
    const answerStart = answerMatch.index;
    const answerTextStart = answerMatch.index + answerMatch[0].length;
    return {
      reasoning: text.slice(reasoningStart, answerStart).trim(),
      answer: cleanAnswerHeading(text.slice(answerTextStart).trim())
    };
  }

  return { reasoning: "", answer: cleanAnswerHeading(text) };
}

function cleanAnswerHeading(value: string) {
  return value.replace(/^\s*(?:最终答案|答案|final answer|answer)\s*[:：]\s*/i, "").trim();
}

function TextBlock({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return <div className={tone ? `qaBlock ${tone}` : "qaBlock"}><label>{label}</label><LatexText value={value} /></div>;
}

function ConversationBlock({ turns, fallback }: { turns: ConversationTurn[]; fallback: string }) {
  if (!turns.length) return <TextBlock label="多轮对话" value={fallback} />;
  return (
    <section className="conversationBlock">
      <label>多轮对话</label>
      <div className="conversationFlow">
        {turns.map((turn, index) => {
          const role = normalizeTurnRole(turn.role);
          if (role === "system") {
            return (
              <details className="conversationSystem" key={`${turn.index ?? index}-system`}>
                <summary>系统</summary>
                <LatexText value={turn.content} />
              </details>
            );
          }
          return (
            <article className={`turn ${role}`} key={`${turn.index ?? index}-${role}`}>
              <div className="turnRole">{roleLabel(role)}</div>
              <div className="turnBody"><LatexText value={turn.content} /></div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function normalizeTurnRole(role: string) {
  const normalized = role.toLowerCase();
  if (["user", "human", "用户"].includes(normalized)) return "user";
  if (["assistant", "gpt", "bot", "model", "助手"].includes(normalized)) return "assistant";
  if (["system", "系统"].includes(normalized)) return "system";
  return "message";
}

function roleLabel(role: string) {
  if (role === "user") return "用户";
  if (role === "assistant") return "助手";
  return "消息";
}

function MediaPreview({ projectId, media }: { projectId: string; media?: string }) {
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const [src, setSrc] = useState("");

  useEffect(() => {
    setFailed(false);
    setZoom(1);
    setExpanded(false);
    setSrc("");
    if (!media) return;
    if (/^(https?:|data:|blob:)/i.test(media)) {
      setSrc(media);
      return;
    }
    let active = true;
    let objectUrl = "";
    api.mediaBlob(projectId, media)
      .then((file) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(file.blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [media, projectId]);

  if (!media) {
    return (
      <div className="mediaViewport empty">
        <FileJson size={34} />
        <span>文本</span>
      </div>
    );
  }

  const zoomOut = () => setZoom((value) => Math.max(0.5, Number((value - 0.25).toFixed(2))));
  const zoomIn = () => setZoom((value) => Math.min(4, Number((value + 0.25).toFixed(2))));
  const resetZoom = () => setZoom(1);
  const renderControls = (showExpand = true) => (
    <div className="mediaTools">
      <button type="button" className="iconButton" onClick={zoomOut} title="缩小"><ZoomOut size={16} /></button>
      <button type="button" className="iconButton" onClick={resetZoom} title="适配">{Math.round(zoom * 100)}%</button>
      <button type="button" className="iconButton" onClick={zoomIn} title="放大"><ZoomIn size={16} /></button>
      {showExpand && <button type="button" className="iconButton" onClick={() => setExpanded(true)} title="查看大图"><Maximize2 size={16} /></button>}
    </div>
  );

  return (
    <div className={failed ? "mediaViewport failed" : "mediaViewport hasImage"}>
      {!failed && renderControls()}
      {!failed && src && <div className="mediaCanvas"><img className="mediaImage" src={src} alt={media} style={{ transform: `scale(${zoom})` }} onError={() => setFailed(true)} /></div>}
      {failed && <Image size={36} />}
      <span>{media}</span>
      {expanded && !failed && (
        <div className="mediaOverlay" role="dialog" aria-modal="true">
          <div className="mediaOverlayBar">
            {renderControls(false)}
            <button type="button" className="iconButton" onClick={() => setExpanded(false)} title="关闭"><X size={16} /></button>
          </div>
          <div className="mediaOverlayCanvas">
            {src && <img src={src} alt={media} style={{ transform: `scale(${zoom})` }} />}
          </div>
        </div>
      )}
    </div>
  );
}

function LatexText({ value }: { value: string }) {
  const parts = parseLatex(value);
  return (
    <p className="latexText">
      {parts.map((part, index) => {
        if (part.type === "text") return <span key={index}>{part.value}</span>;
        const html = renderLatex(part.value, part.display);
        return html ? (
          <span
            key={index}
            className={part.display ? "mathBlock" : "mathInline"}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        ) : (
          <code key={index}>{part.raw}</code>
        );
      })}
    </p>
  );
}

type LatexPart = { type: "text"; value: string } | { type: "math"; value: string; raw: string; display: boolean };

function parseLatex(input: string): LatexPart[] {
  const text = normalizeLatexDelimiters(input);
  const parts: LatexPart[] = [];
  const pattern = /(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|\$(?!\s)(?:\\.|[^$])+?(?<!\s)\$)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const raw = match[0];
    const index = match.index ?? 0;
    if (index > cursor) parts.push({ type: "text", value: text.slice(cursor, index) });
    const display = raw.startsWith("\\[") || raw.startsWith("$$");
    const value = raw.startsWith("\\(") || raw.startsWith("\\[") ? raw.slice(2, -2) : raw.slice(display ? 2 : 1, display ? -2 : -1);
    parts.push({ type: "math", value, raw, display });
    cursor = index + raw.length;
  }
  if (cursor < text.length) parts.push({ type: "text", value: text.slice(cursor) });
  return parts;
}

function normalizeLatexDelimiters(input: string) {
  return input
    .replace(/\\\\\(/g, "\\(")
    .replace(/\\\\\)/g, "\\)")
    .replace(/\\\\\[/g, "\\[")
    .replace(/\\\\\]/g, "\\]")
    .replace(/\\times/g, "\\times");
}

function renderLatex(value: string, displayMode: boolean) {
  try {
    return katex.renderToString(value, {
      displayMode,
      throwOnError: false,
      strict: "ignore",
      trust: false,
      output: "html"
    });
  } catch {
    return "";
  }
}

function Step({ label, value, score, done }: { label: string; value: string; score: string; done?: boolean }) {
  return (
    <div className={done ? "step done" : "step"}>
      <span className="stepIcon">{done ? <Check size={14} /> : <RefreshCcw size={14} />}</span>
      <div><strong>{label}</strong><p>{value}</p></div>
      <code>{score}</code>
    </div>
  );
}

function Shortcut({ action, keyName }: { action: string; keyName: string }) {
  return <p className="shortcut"><span>{action}</span><kbd>{keyName}</kbd></p>;
}

function StatusBadge({ status, compact }: { status: ReviewStatus; compact?: boolean }) {
  return <span className={`status ${compact ? "compact " : ""}${status.toLowerCase()}`}>人工 {statusText[status]}</span>;
}

function AiBadge({ status, compact }: { status: string; compact?: boolean }) {
  return <span className={`status aiStatus ${compact ? "compact " : ""}${status.toLowerCase()}`}>AI {aiDecisionText[status] ?? status}</span>;
}

function Progress({ value }: { value: number }) {
  return <div className="progress" aria-label={`进度 ${Math.round(value)}%`}><span style={{ width: `${Math.max(0, Math.min(value, 100))}%` }} /></div>;
}
