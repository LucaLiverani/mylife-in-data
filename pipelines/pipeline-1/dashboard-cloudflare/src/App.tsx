import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Spotify from './pages/Spotify';
import YouTube from './pages/YouTube';
import Google from './pages/Google';
import Maps from './pages/Maps';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/spotify" element={<Spotify />} />
        <Route path="/youtube" element={<YouTube />} />
        <Route path="/google" element={<Google />} />
        <Route path="/maps" element={<Maps />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
