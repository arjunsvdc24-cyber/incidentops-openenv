import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { Layout } from './components/Layout';
import { AuthModal } from './components/AuthModal';
import { Toast } from './components/Toast';
import { PageTransition } from './components/Animations';
import { DashboardPage } from './pages/DashboardPage';
import { EpisodePage } from './pages/EpisodePage';
import { TasksPage } from './pages/TasksPage';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { EpisodesPage } from './pages/EpisodesPage';
import { ReplayPage } from './pages/ReplayPage';
import { ProfilePage } from './pages/ProfilePage';
import { ValidationPage } from './pages/ValidationPage';
import { useAuthStore } from './stores/episodeStore';

function AppContent() {
  const { loadFromStorage } = useAuthStore();

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<PageTransition><DashboardPage /></PageTransition>} />
        <Route path="/episode" element={<PageTransition><EpisodePage /></PageTransition>} />
        <Route path="/tasks" element={<PageTransition><TasksPage /></PageTransition>} />
        <Route path="/leaderboard" element={<PageTransition><LeaderboardPage /></PageTransition>} />
        <Route path="/episodes" element={<PageTransition><EpisodesPage /></PageTransition>} />
        <Route path="/replay/:id" element={<PageTransition><ReplayPage /></PageTransition>} />
        <Route path="/profile" element={<PageTransition><ProfilePage /></PageTransition>} />
        <Route path="/validate" element={<PageTransition><ValidationPage /></PageTransition>} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
      <AuthModal />
      <Toast />
    </BrowserRouter>
  );
}
