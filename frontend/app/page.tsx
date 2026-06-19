import Chatbot from '@/components/Chatbot'
import { Bell, HelpCircle, RotateCcw, AlertTriangle, Settings, Plus, MessageSquare, Bot, Layout } from 'lucide-react';

export default function Home() {
  return (
    <div className="flex flex-col h-screen bg-white font-sans text-gray-800">
      {/* Top Navbar */}
      <header className="flex items-center justify-between px-8 py-3.5 bg-[#0066cc] text-white z-20">
        <div className="text-[22px] font-medium tracking-wide">Elixir Portal 3.0</div>
        <div className="flex items-center space-x-6">
          <button className="hover:text-gray-200 transition-colors"><Bell size={20} /></button>
          <button className="hover:text-gray-200 transition-colors"><HelpCircle size={20} /></button>
          <div className="w-8 h-8 rounded-full overflow-hidden bg-white/20 cursor-pointer">
            <img src="https://ui-avatars.com/api/?name=Akshay+Poojari&background=random" alt="User" className="w-full h-full object-cover" />
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <aside className="w-[260px] bg-[#f8f9fa] border-r border-gray-100 flex flex-col z-10">
          <div className="flex flex-col items-center pt-8 pb-6">
            <div className="bg-[#0066cc] p-2.5 rounded-[14px] mb-3 shadow-sm">
              <Bot size={32} className="text-white" />
            </div>
            <h2 className="text-[#0052a3] text-xl font-bold tracking-tight">Elixir AI</h2>
          </div>

          <div className="px-5 mb-6">
            <button className="w-full flex items-center justify-center gap-2 bg-[#005cbf] hover:bg-[#004b99] text-white py-2.5 rounded-md font-medium transition-colors shadow-sm text-sm">
              <Plus size={18} />
              New Support Ticket
            </button>
          </div>

          <nav className="flex-1 px-3 space-y-1">
            <a href="#" className="flex items-center gap-3 px-3 py-3 bg-[#d9e8ff] text-[#0052a3] rounded-lg font-medium border border-[#cce0ff]">
              <MessageSquare size={18} />
              <span className="text-[15px]">Current Chat</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-3 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
              <RotateCcw size={18} />
              <span className="text-[15px]">History</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-3 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
              <Layout size={18} />
              <span className="text-[15px]">Service Catalog</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-3 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
              <AlertTriangle size={18} />
              <span className="text-[15px]">Incidents</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-3 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
              <Settings size={18} />
              <span className="text-[15px]">Settings</span>
            </a>
          </nav>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col bg-[#fafbfc] relative">

          {/* Scrollable container for tickets and chat */}
          <div className="flex-1 flex flex-col items-center pt-8 px-6 overflow-hidden">

            {/* Top Ticket Widget */}
            {/* <div className="w-full max-w-[850px] bg-white border border-gray-200 rounded-lg shadow-sm mb-6 flex-shrink-0">
              <div className="p-5 border-b border-gray-100"> */}
            {/* <div className="flex justify-between items-start mb-5">
                  <div>
                    <div className="text-[10px] text-gray-400 font-bold mb-1 uppercase tracking-widest">SUBJECT</div>
                    <div className="text-lg font-bold text-gray-800">SAP PRD Password Reset</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-gray-400 font-bold mb-1 uppercase tracking-widest">STATUS</div>
                    <div className="text-[#0066cc] border border-[#0066cc] bg-blue-50/50 px-2.5 py-0.5 rounded text-[13px] font-semibold">In Progress</div>
                  </div>
                </div> */}

            {/* <div className="flex justify-between items-end">
                  <div>
                    <div className="text-[10px] text-gray-400 font-bold mb-1 uppercase tracking-widest">REQUESTED FOR</div>
                    <div className="text-[15px] text-gray-800">Akshay Poojari</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-gray-400 font-bold mb-1 uppercase tracking-widest">PRIORITY</div>
                    <div className="bg-[#fcdab7] text-[#8a4e12] px-3 py-0.5 rounded text-[13px] font-bold inline-block">Medium</div>
                  </div>
                </div>
              </div>
              <div className="bg-[#f8f9fa] px-5 py-3 flex justify-between items-center text-[13px] rounded-b-lg">
                <span className="text-gray-500">Estimated resolution: 2 hours</span>
                <a href="#" className="text-[#0066cc] font-semibold hover:underline tracking-wide text-[12px]">VIEW DETAILS</a>
              </div>
            </div> */}

            {/* Chatbot Interface - Takes up remaining height perfectly */}
            <div className="w-full max-w-[850px] flex-1 flex flex-col min-h-0 pb-6">
              <Chatbot />
            </div>

          </div>

          {/* Footer */}
          <footer className="bg-white border-t border-gray-200 py-3 px-8 flex justify-between text-[13px] text-gray-500 shrink-0">
            <div>© 2026 Elixir AI</div>
            <div className="flex space-x-6">
              <a href="#" className="hover:text-gray-800 transition-colors">Privacy Policy</a>
              <a href="#" className="hover:text-gray-800 transition-colors">Terms of Service</a>
              <a href="#" className="hover:text-gray-800 transition-colors">Security</a>
            </div>
          </footer>
        </main>
      </div>
    </div>
  )
}
