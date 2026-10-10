import { NavLink, Route, Routes } from "react-router-dom";
import Overview from "./pages/Overview";
import Sources from "./pages/Sources";
import News from "./pages/News";
import Topics from "./pages/Topics";
import Research from "./pages/Research";
import Articles from "./pages/Articles";
import ArticleDetail from "./pages/ArticleDetail";
import Media from "./pages/Media";
import Review from "./pages/Review";
import Publishing from "./pages/Publishing";
import Metrics from "./pages/Metrics";
import Analytics from "./pages/Analytics";
import Tasks from "./pages/Tasks";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "运营总览" },
  { to: "/news", label: "资讯列表" },
  { to: "/topics", label: "选题池" },
  { to: "/research", label: "研究与核验" },
  { to: "/articles", label: "文章管理" },
  { to: "/review", label: "审核队列" },
  { to: "/media", label: "图片素材" },
  { to: "/publishing", label: "发布记录" },
  { to: "/metrics", label: "阅读与收益" },
  { to: "/analytics", label: "栏目分析" },
  { to: "/tasks", label: "任务中心" },
  { to: "/sources", label: "资讯源" },
  { to: "/settings", label: "系统设置" },
];

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">玄知见解</div>
        <div className="logo-sub">AI 科技内容运营台</div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/news" element={<News />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/research" element={<Research />} />
          <Route path="/articles" element={<Articles />} />
          <Route path="/articles/:id" element={<ArticleDetail />} />
          <Route path="/media" element={<Media />} />
          <Route path="/review" element={<Review />} />
          <Route path="/publishing" element={<Publishing />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
