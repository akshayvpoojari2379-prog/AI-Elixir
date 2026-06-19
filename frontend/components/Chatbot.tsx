'use client';
import { useState, useRef, useEffect } from 'react';
import {
  Send, Bot, User, Paperclip, CheckCircle,
  Moon, Sun, Sparkles, AlertCircle, ShieldAlert, Cpu,
  PenTool, Building, CheckSquare, FileText, Key, HelpCircle
} from 'lucide-react';
import axios from 'axios';

interface Source {
  id: number;
  title: string;
  type: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  needs_ticket?: boolean;
  ticket_id?: string;
  image_data?: string;
}

interface OptionItem {
  title: string;
  description: string;
}

const parseStructuredOptions = (text: string) => {
  const lines = text.split('\n');
  const introLines: string[] = [];
  const options: OptionItem[] = [];
  let isOptionSection = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('*') || trimmed.startsWith('-')) {
      const match = trimmed.match(/^[\*\-]\s+\*?\*?([^\:\-\*]+)\*?\*?[\:\-]?\s*(.*)$/);
      if (match) {
        const title = match[1].trim().replace(/\*+/g, '');
        const description = match[2].trim().replace(/\*+/g, '');
        // Only parse as option if it has a description or title is a short action link (<= 40 chars)
        if (title.length > 0 && (description.length > 0 || title.length <= 40)) {
          isOptionSection = true;
          options.push({ title, description });
          continue;
        }
      }
      introLines.push(line);
    } else {
      if (!isOptionSection) {
        introLines.push(line);
      } else {
        if (options.length > 0 && trimmed) {
          options[options.length - 1].description += ' ' + trimmed;
        } else if (trimmed) {
          introLines.push(line);
        }
      }
    }
  }

  return {
    hasOptions: options.length > 0,
    intro: introLines.join('\n').trim(),
    options
  };
};

const getOptionIcon = (title: string) => {
  const t = title.toLowerCase();
  if (t.includes('esign') || t.includes('e-sign') || t.includes('signing')) {
    return <PenTool className="w-5 h-5 text-indigo-500" />;
  }
  if (t.includes('supplier') || t.includes('onboarding') || t.includes('profile')) {
    return <Building className="w-5 h-5 text-blue-500" />;
  }
  if (t.includes('approval') || t.includes('matrix') || t.includes('threshold')) {
    return <CheckSquare className="w-5 h-5 text-emerald-500" />;
  }
  if (t.includes('contract') || t.includes('cdr')) {
    return <FileText className="w-5 h-5 text-violet-500" />;
  }
  if (t.includes('portal') || t.includes('login') || t.includes('sso')) {
    return <Key className="w-5 h-5 text-amber-500" />;
  }
  return <HelpCircle className="w-5 h-5 text-slate-500" />;
};

// Block parser and markdown renderer utilities
interface Block {
  type: 'paragraph' | 'heading3' | 'heading4' | 'heading5' | 'bullet_list' | 'numbered_list' | 'blockquote' | 'hr';
  lines: string[];
  alertType?: 'important' | 'tip' | 'warning' | 'normal';
}

const parseBlocks = (text: string): Block[] => {
  const lines = text.split('\n');
  const blocks: Block[] = [];
  let currentBlock: Block | null = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Horizontal Rule
    if (trimmed === '***' || trimmed === '---') {
      if (currentBlock) {
        blocks.push(currentBlock);
        currentBlock = null;
      }
      blocks.push({ type: 'hr', lines: [line] });
      continue;
    }

    // Headings
    if (trimmed.startsWith('### ')) {
      if (currentBlock) {
        blocks.push(currentBlock);
        currentBlock = null;
      }
      blocks.push({ type: 'heading3', lines: [trimmed.slice(4)] });
      continue;
    }
    if (trimmed.startsWith('#### ')) {
      if (currentBlock) {
        blocks.push(currentBlock);
        currentBlock = null;
      }
      blocks.push({ type: 'heading4', lines: [trimmed.slice(5)] });
      continue;
    }
    if (trimmed.startsWith('##### ')) {
      if (currentBlock) {
        blocks.push(currentBlock);
        currentBlock = null;
      }
      blocks.push({ type: 'heading5', lines: [trimmed.slice(6)] });
      continue;
    }

    // Blockquote / Alerts
    if (trimmed.startsWith('>')) {
      let content = line.substring(line.indexOf('>') + 1);
      if (content.startsWith(' ')) {
        content = content.substring(1);
      }

      if (currentBlock && currentBlock.type === 'blockquote') {
        currentBlock.lines.push(content);
      } else {
        if (currentBlock) {
          blocks.push(currentBlock);
        }
        currentBlock = { type: 'blockquote', lines: [content] };
      }
      continue;
    }

    // Bullet list
    const bulletMatch = line.match(/^(\s*)([\-\*])\s+(.*)$/);
    if (bulletMatch) {
      const content = bulletMatch[3];
      if (currentBlock && currentBlock.type === 'bullet_list') {
        currentBlock.lines.push(content);
      } else {
        if (currentBlock) {
          blocks.push(currentBlock);
        }
        currentBlock = { type: 'bullet_list', lines: [content] };
      }
      continue;
    }

    // Numbered list
    const numMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
    if (numMatch) {
      const content = numMatch[3];
      if (currentBlock && currentBlock.type === 'numbered_list') {
        currentBlock.lines.push(content);
      } else {
        if (currentBlock) {
          blocks.push(currentBlock);
        }
        currentBlock = { type: 'numbered_list', lines: [content] };
      }
      continue;
    }

    // Paragraph/Blank lines
    if (trimmed === '') {
      if (currentBlock) {
        blocks.push(currentBlock);
        currentBlock = null;
      }
      continue;
    }

    if (currentBlock && currentBlock.type === 'paragraph') {
      currentBlock.lines.push(line);
    } else {
      if (currentBlock) {
        blocks.push(currentBlock);
      }
      currentBlock = { type: 'paragraph', lines: [line] };
    }
  }

  if (currentBlock) {
    blocks.push(currentBlock);
  }

  // Post-process blockquotes for alerts
  blocks.forEach(b => {
    if (b.type === 'blockquote' && b.lines.length > 0) {
      const firstLine = b.lines[0].trim().toUpperCase();
      if (firstLine.includes('[!IMPORTANT]') || firstLine.includes('[!NOTE]')) {
        b.alertType = 'important';
        b.lines.shift();
      } else if (firstLine.includes('[!TIP]')) {
        b.alertType = 'tip';
        b.lines.shift();
      } else if (firstLine.includes('[!WARNING]') || firstLine.includes('[!CAUTION]')) {
        b.alertType = 'warning';
        b.lines.shift();
      } else {
        b.alertType = 'normal';
      }
    }
  });

  return blocks;
};

const renderInlineText = (text: string) => {
  const regex = /(\*\*`[^`]+`\*\*|\*\*.*?\*\*|`[^`]+`)/g;
  const parts = text.split(regex);
  return parts.map((part, index) => {
    if (part.startsWith('**`') && part.endsWith('`**')) {
      const val = part.slice(3, -3);
      return (
        <code key={index} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50 font-mono text-[13px] font-bold text-indigo-600 dark:text-indigo-400">
          {val}
        </code>
      );
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      const val = part.slice(2, -2);
      if (val.startsWith('`') && val.endsWith('`')) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50 font-mono text-[13px] font-bold text-indigo-600 dark:text-indigo-400">
            {val.slice(1, -1)}
          </code>
        );
      }
      return <strong key={index} className="font-bold text-slate-900 dark:text-white">{val}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      const val = part.slice(1, -1);
      return (
        <code key={index} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200/50 dark:border-slate-700/50 font-mono text-[13px] font-semibold text-slate-800 dark:text-slate-250">
          {val}
        </code>
      );
    }
    return part;
  });
};

const MarkdownRenderer = ({ content }: { content: string }) => {
  const blocks = parseBlocks(content);

  return (
    <div className="flex flex-col gap-2.5 text-left w-full">
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'hr':
            return <hr key={idx} className="my-2 border-slate-200 dark:border-slate-800/80" />;
          case 'heading3':
            return (
              <h3 key={idx} className="text-[17px] font-extrabold text-slate-800 dark:text-white tracking-tight mt-3 mb-1">
                {renderInlineText(block.lines.join(' '))}
              </h3>
            );
          case 'heading4':
            return (
              <h4 key={idx} className="text-[15px] font-bold text-slate-800 dark:text-slate-100 tracking-tight mt-2 mb-1">
                {renderInlineText(block.lines.join(' '))}
              </h4>
            );
          case 'heading5':
            return (
              <h5 key={idx} className="text-[13px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mt-2 mb-0.5">
                {renderInlineText(block.lines.join(' '))}
              </h5>
            );
          case 'bullet_list':
            return (
              <ul key={idx} className="list-disc pl-5 space-y-1.5 text-slate-600 dark:text-slate-350">
                {block.lines.map((line, lIdx) => (
                  <li key={lIdx} className="text-[14.5px] leading-relaxed">
                    {renderInlineText(line)}
                  </li>
                ))}
              </ul>
            );
          case 'numbered_list':
            return (
              <ol key={idx} className="list-decimal pl-5 space-y-1.5 text-slate-650 dark:text-slate-350">
                {block.lines.map((line, lIdx) => (
                  <li key={lIdx} className="text-[14.5px] leading-relaxed">
                    {renderInlineText(line)}
                  </li>
                ))}
              </ol>
            );
          case 'blockquote':
            if (block.alertType === 'important') {
              return (
                <div key={idx} className="flex gap-3.5 p-4 rounded-2xl border bg-blue-50/40 dark:bg-blue-950/10 border-blue-200/60 dark:border-blue-900/30 text-blue-800 dark:text-blue-200 my-2">
                  <div className="p-1.5 bg-blue-100/50 dark:bg-blue-900/40 rounded-xl self-start">
                    <AlertCircle className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div className="flex-1 text-[13.5px] leading-relaxed font-medium">
                    {renderInlineText(block.lines.join(' '))}
                  </div>
                </div>
              );
            }
            if (block.alertType === 'tip') {
              return (
                <div key={idx} className="flex gap-3.5 p-4 rounded-2xl border bg-emerald-50/40 dark:bg-emerald-950/10 border-emerald-200/60 dark:border-emerald-900/30 text-emerald-800 dark:text-emerald-250 my-2">
                  <div className="p-1.5 bg-emerald-100/50 dark:bg-emerald-900/40 rounded-xl self-start">
                    <Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div className="flex-1 text-[13.5px] leading-relaxed font-medium">
                    {renderInlineText(block.lines.join(' '))}
                  </div>
                </div>
              );
            }
            if (block.alertType === 'warning') {
              return (
                <div key={idx} className="flex gap-3.5 p-4 rounded-2xl border bg-amber-50/40 dark:bg-amber-950/10 border-amber-200/60 dark:border-amber-900/30 text-amber-800 dark:text-amber-200 my-2">
                  <div className="p-1.5 bg-amber-100/50 dark:bg-amber-900/40 rounded-xl self-start">
                    <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div className="flex-1 text-[13.5px] leading-relaxed font-medium">
                    {renderInlineText(block.lines.join(' '))}
                  </div>
                </div>
              );
            }
            return (
              <blockquote key={idx} className="pl-4 border-l-4 border-slate-200 dark:border-slate-800/80 italic text-slate-500 dark:text-slate-400 my-2 text-[14px]">
                {renderInlineText(block.lines.join(' '))}
              </blockquote>
            );
          case 'paragraph':
          default:
            return (
              <p key={idx} className="text-[14.5px] leading-relaxed text-slate-700 dark:text-slate-300">
                {renderInlineText(block.lines.join(' '))}
              </p>
            );
        }
      })}
    </div>
  );
};

interface TicketDetails {
  ticketId: string;
  type: string;
  subject: string;
  group: string;
  status: string;
}

const parseTicketDetails = (content: string, ticketIdFromMessage?: string): TicketDetails | null => {
  const isTicketMsg = content.includes("Ticket Reference:") || content.includes("raised a Freshservice");
  if (!isTicketMsg) return null;

  let ticketId = ticketIdFromMessage || "";
  const idMatch = content.match(/Ticket Reference:\*\*?\s*#?([A-Za-z0-9\-]+)/i);
  if (idMatch) {
    ticketId = idMatch[1].replace(/\*+/g, "").trim();
  }

  let type = "Service Request";
  if (content.toLowerCase().includes("incident")) {
    type = "Incident";
  }

  let subject = "Laptop purchase order";
  const subjectMatch = content.match(/Subject:\*\*?\s*([^\n]+)/i);
  if (subjectMatch) {
    subject = subjectMatch[1].replace(/\*+/g, "").trim();
  }

  let group = "IT Support Desk";
  const groupMatch = content.match(/Assignment Group:\*\*?\s*([^\n]+)/i);
  if (groupMatch) {
    group = groupMatch[1].replace(/\*+/g, "").trim();
  }

  let status = "Open / Dispatched";
  const statusMatch = content.match(/Status:\*\*?\s*([^\n]+)/i);
  if (statusMatch) {
    status = statusMatch[1].replace(/\*+/g, "").trim();
    if (status.includes("Our support")) {
      status = status.split("Our support")[0].trim();
    }
  }

  return {
    ticketId,
    type,
    subject,
    group,
    status
  };
};

export default function Chatbot() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I am your Elixir AI Support Assistant. I am backed by a multi-agent orchestration engine to resolve your queries deterministically or auto-generate tickets. How can I help you today?',
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [attachment, setAttachment] = useState<{ name: string; data: string } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      setAttachment({
        name: file.name,
        data: reader.result as string
      });
    };
    reader.readAsDataURL(file);
    if (e.target) {
      e.target.value = '';
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleQuickAction = async (text: string) => {
    setInput('');
    await submitMessage(text);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const msgText = input;
    setInput('');
    await submitMessage(msgText);
  };

  const submitMessage = async (text: string) => {
    const isImg = attachment && attachment.name.match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i);
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text + (attachment && !isImg ? ` [Attached: ${attachment.name}]` : ''),
      image_data: isImg ? attachment.data : undefined
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    const fileDataToSend = attachment ? attachment.data : undefined;
    const fileNameToSend = attachment ? attachment.name : undefined;
    setAttachment(null);

    try {
      const response = await axios.post((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/v1/chat', {
        message: text,
        session_id: sessionId,
        file_data: fileDataToSend,
        file_name: fileNameToSend
      });

      if (!sessionId) {
        setSessionId(response.data.session_id);
      }

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.message,
        sources: response.data.sources,
        needs_ticket: response.data.needs_ticket,
        ticket_id: response.data.ticket_id
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please ensure the backend and Ollama are running.',
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const createTicket = async (description: string) => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const response = await axios.post((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/v1/ticket/create', {
        session_id: sessionId,
        description: description,
        type: 'Incident'
      });

      const ticketId = response.data.ticket_id;

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `### Ticket Successfully Created!\n\n**Incident Reference:** #${ticketId}\n\nOur specialized IT service desk group has been notified and dispatched to handle your request.`,
        ticket_id: ticketId
      }]);

      alert(`Ticket #${ticketId} created successfully!`);
    } catch (error) {
      alert('Failed to create ticket.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`premium-font w-full h-[88vh] flex items-center justify-center p-4 transition-all duration-500 mesh-glow-bg ${darkMode ? 'dark bg-[#07090e]' : 'bg-[#f4f7fa]'}`}>

      {/* Dynamic Embedded CSS */}
      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

        .premium-font {
          font-family: 'Plus Jakarta Sans', sans-serif;
        }

        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(16px) scale(0.99);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        .animate-message-fade {
          animation: fadeInUp 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes meshShift {
          0% { background-position: 0% 50% }
          50% { background-position: 100% 50% }
          100% { background-position: 0% 50% }
        }

        .mesh-glow-bg {
          background: radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.12) 0%, transparent 35%),
                      radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.12) 0%, transparent 35%),
                      radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.05) 0%, transparent 55%);
          background-size: 200% 200%;
          animation: meshShift 16s ease infinite;
        }

        .dark.mesh-glow-bg {
          background: radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.07) 0%, transparent 30%),
                      radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.07) 0%, transparent 30%),
                      radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.02) 0%, transparent 45%);
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 5px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.18);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(148, 163, 184, 0.3);
        }
        
        .glass-panel {
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
        }
      `}</style>

      {/* Main Container */}
      <div className={`glass-panel w-full max-w-5xl h-full rounded-[32px] border flex flex-col overflow-hidden shadow-[0_24px_64px_-16px_rgba(0,0,0,0.08)] dark:shadow-[0_24px_64px_-16px_rgba(0,0,0,0.35)] transition-all duration-500 ${darkMode
        ? 'bg-[#0f131c]/80 border-slate-800/80 text-[#f8fafc]'
        : 'bg-white/80 border-slate-200/60 text-[#1e293b]'
        }`}>

        {/* Sleek Header */}
        <div className={`flex items-center justify-between px-8 py-5 border-b backdrop-blur-md transition-colors duration-500 ${darkMode ? 'bg-slate-900/40 border-slate-800/80' : 'bg-white/40 border-slate-100'
          }`}>
          <div className="flex items-center gap-4">
            <div className="relative flex items-center justify-center w-11 h-11 rounded-2xl bg-gradient-to-tr from-[#6366f1] to-[#8b5cf6] shadow-[0_4px_16px_rgba(99,102,241,0.35)] hover:scale-105 active:scale-95 transition-all duration-300">
              <Bot className="w-5.5 h-5.5 text-white" />
              <span className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-500 rounded-full border-2 border-white dark:border-[#0f131c] animate-pulse"></span>
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight" style={{ color: darkMode ? '#ffffff' : '#0f172a' }}>Elixir AI</h1>
              <p className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1.5 mt-0.5">
                <Cpu className="w-3.5 h-3.5 text-[#6366f1] animate-spin" style={{ animationDuration: '4s' }} /> Elixir Support Assistant
              </p>
            </div>
          </div>

          <button
            onClick={() => setDarkMode(!darkMode)}
            className={`p-3 rounded-2xl border transition-all hover:scale-105 active:scale-95 shadow-sm ${darkMode
              ? 'bg-slate-800/60 border-slate-700/80 text-amber-400 hover:bg-slate-700/60'
              : 'bg-white border-slate-200/60 text-slate-500 hover:bg-slate-50'
              }`}
          >
            {darkMode ? <Sun className="w-4.5 h-4.5" /> : <Moon className="w-4.5 h-4.5" />}
          </button>
        </div>

        {/* Chat Bubbles Scroller */}
        <div className="flex-1 overflow-y-auto px-8 py-8 space-y-6 custom-scrollbar">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-message-fade`}
            >
              <div className={`flex max-w-[85%] gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>

                {/* Avatar Icon */}
                <div className={`flex-shrink-0 h-10 w-10 rounded-[14px] flex items-center justify-center shadow-md transition-all duration-300 ${msg.role === 'user'
                  ? 'bg-gradient-to-tr from-[#6366f1] to-[#8b5cf6] text-white shadow-[0_4px_12px_rgba(99,102,241,0.25)]'
                  : darkMode
                    ? 'bg-slate-900/60 border border-slate-800/80 text-blue-400'
                    : 'bg-white border border-slate-200/60 text-[#6366f1]'
                  }`}>
                  {msg.role === 'user' ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
                </div>

                {/* Text & Meta Container */}
                <div className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} w-full`}>

                  {/* Bubble body (Option Card Parsing or Default text) */}
                  {(() => {
                    if (msg.role === 'user') {
                      return (
                        <div className="flex flex-col gap-2 items-end">
                          {msg.image_data && (
                            <div className="relative rounded-2xl overflow-hidden border border-slate-200/50 dark:border-slate-800/80 shadow-md max-w-xs transition-transform duration-300 hover:scale-[1.02] bg-white dark:bg-slate-900 p-1">
                              <img src={msg.image_data} alt="Uploaded attachment" className="max-h-60 w-auto object-cover rounded-xl" />
                            </div>
                          )}
                          {msg.content.trim() && (
                            <div className="px-5 py-3.5 rounded-2xl shadow-[0_2px_8px_rgba(0,0,0,0.02)] text-[15px] leading-relaxed transition-all duration-300 border bg-gradient-to-tr from-[#6366f1] to-[#8b5cf6] text-white border-transparent rounded-tr-none shadow-[0_4px_16px_rgba(99,102,241,0.3)]">
                              <p className="whitespace-pre-wrap">{msg.content}</p>
                            </div>
                          )}
                        </div>
                      );
                    }

                    const ticket = parseTicketDetails(msg.content, msg.ticket_id);
                    if (ticket) {
                      const isIncident = ticket.type === "Incident";
                      return (
                        <div className={`w-full max-w-lg rounded-[28px] border p-6 transition-all duration-500 animate-message-fade flex flex-col gap-5 text-left shadow-2xl relative overflow-hidden ${darkMode
                          ? 'bg-[#121824]/90 border-slate-800/80 shadow-[0_20px_50px_rgba(99,102,241,0.08)] text-slate-100'
                          : 'bg-white border-slate-200/60 shadow-[0_20px_50px_rgba(99,102,241,0.06)] text-slate-800'
                          }`}>
                          {/* Glowing corner accents */}
                          <div className={`absolute top-0 right-0 w-24 h-24 rounded-full filter blur-[40px] opacity-20 -mr-6 -mt-6 ${isIncident ? 'bg-rose-500' : 'bg-indigo-500'
                            }`} />

                          {/* Top Header Badge */}
                          <div className="flex items-center justify-between border-b pb-4 border-slate-100 dark:border-slate-800/60 relative z-10">
                            <div className="flex items-center gap-3">
                              <div className={`p-3 rounded-2xl flex items-center justify-center shadow-sm ${isIncident
                                ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-500'
                                : 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-500'
                                }`}>
                                {isIncident ? <AlertCircle className="w-6 h-6 animate-pulse" /> : <Sparkles className="w-6 h-6 animate-pulse" />}
                              </div>
                              <div>
                                <h4 className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400 dark:text-slate-500">Freshservice Auto-Dispatch</h4>
                                <span className={`text-[11px] font-bold px-3 py-0.5 rounded-full mt-1.5 inline-block ${isIncident
                                  ? 'bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 border border-rose-100/50 dark:border-rose-900/30'
                                  : 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-100/50 dark:border-indigo-900/30'
                                  }`}>
                                  {ticket.type}
                                </span>
                              </div>
                            </div>
                            <div className="text-right">
                              <span className="text-[9px] font-extrabold text-slate-400 dark:text-slate-500 block uppercase tracking-widest">Ticket Reference</span>
                              <span className="text-lg font-black tracking-tight bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] bg-clip-text text-transparent mt-0.5 block">
                                #{ticket.ticketId}
                              </span>
                            </div>
                          </div>

                          {/* Details List */}
                          <div className="flex flex-col gap-3 py-1 relative z-10">
                            {/* Subject */}
                            <div className={`flex items-start gap-3.5 p-3.5 rounded-2xl border transition-colors ${darkMode ? 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900/60' : 'bg-slate-50/50 border-slate-200/40 hover:bg-slate-50'
                              }`}>
                              <div className={`p-2 rounded-xl shrink-0 mt-0.5 ${darkMode ? 'bg-slate-800 text-indigo-400' : 'bg-indigo-50 text-indigo-600'}`}>
                                <FileText className="w-4 h-4" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400 dark:text-slate-500">Subject</p>
                                <p className="font-bold text-[14px] text-slate-800 dark:text-slate-100 leading-relaxed mt-0.5 break-words">
                                  {ticket.subject}
                                </p>
                              </div>
                            </div>

                            {/* Assignment Group */}
                            <div className={`flex items-start gap-3.5 p-3.5 rounded-2xl border transition-colors ${darkMode ? 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900/60' : 'bg-slate-50/50 border-slate-200/40 hover:bg-slate-50'
                              }`}>
                              <div className={`p-2 rounded-xl shrink-0 mt-0.5 ${darkMode ? 'bg-slate-800 text-violet-400' : 'bg-violet-50 text-violet-600'}`}>
                                <Building className="w-4 h-4" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400 dark:text-slate-500">Assignment Group</p>
                                <p className="font-bold text-[14px] text-slate-800 dark:text-slate-200 leading-relaxed mt-0.5">
                                  {ticket.group}
                                </p>
                              </div>
                            </div>

                            {/* Status */}
                            <div className={`flex items-start gap-3.5 p-3.5 rounded-2xl border transition-colors ${darkMode ? 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900/60' : 'bg-slate-50/50 border-slate-200/40 hover:bg-slate-50'
                              }`}>
                              <div className={`p-2 rounded-xl shrink-0 mt-0.5 ${darkMode ? 'bg-slate-800 text-emerald-400' : 'bg-emerald-50 text-emerald-600'}`}>
                                <CheckSquare className="w-4 h-4" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400 dark:text-slate-500">Status</p>
                                <div className="flex items-center gap-2 mt-1">
                                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0"></span>
                                  <span className="font-extrabold text-[13px] text-emerald-600 dark:text-emerald-400 leading-none">
                                    {ticket.status}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Footer Info Notice */}
                          <div className={`rounded-2xl p-4 border text-left flex items-start gap-3 relative z-10 ${darkMode ? 'bg-slate-900/30 border-slate-800/60' : 'bg-slate-50 border-slate-200/30'
                            }`}>
                            <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${darkMode ? 'bg-slate-800 text-slate-400' : 'bg-white text-slate-400'}`}>
                              <HelpCircle className="w-4 h-4" />
                            </div>
                            <p className="text-[11.5px] leading-relaxed text-slate-500 dark:text-slate-400 font-medium">
                              Our support desk resolves issues within SLA windows. A notification alert card has also been sent to Microsoft Teams for immediate validation.
                            </p>
                          </div>
                        </div>
                      );
                    }

                    const parsed = parseStructuredOptions(msg.content);
                    if (parsed.hasOptions) {
                      return (
                        <div className="flex flex-col gap-4.5 w-full">
                          {parsed.intro && (
                            <div className={`px-5 py-3.5 rounded-2xl shadow-sm text-[15px] leading-relaxed border rounded-tl-none ${darkMode
                              ? 'bg-slate-800/40 text-slate-200 border-slate-800/80'
                              : 'bg-white text-slate-800 border-slate-200/50'
                              }`}>
                              <MarkdownRenderer content={parsed.intro} />
                            </div>
                          )}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-3xl">
                            {parsed.options.map((opt, idx) => (
                              <div
                                key={idx}
                                onClick={() => handleQuickAction(opt.title)}
                                className={`p-5 rounded-[20px] border transition-all duration-300 hover:-translate-y-1 hover:shadow-lg active:scale-95 cursor-pointer flex flex-col gap-3.5 group ${darkMode
                                  ? 'bg-[#151c2c]/80 hover:bg-[#1b253b] border-slate-800 hover:border-[#6366f1]/40'
                                  : 'bg-white hover:bg-slate-50/50 border-slate-200/50 hover:border-[#6366f1]/30'
                                  }`}
                              >
                                <div className="flex items-center gap-3">
                                  <div className={`p-2.5 rounded-xl transition-all ${darkMode
                                    ? 'bg-slate-900/60 group-hover:bg-[#6366f1]/10'
                                    : 'bg-slate-50 group-hover:bg-[#6366f1]/5'
                                    }`}>
                                    {getOptionIcon(opt.title)}
                                  </div>
                                  <h4 className="font-bold text-[14px] text-slate-800 dark:text-slate-200 group-hover:text-[#6366f1] dark:group-hover:text-[#8b5cf6] transition-colors leading-tight">
                                    {opt.title}
                                  </h4>
                                </div>
                                <p className="text-[12.5px] leading-relaxed text-slate-400 dark:text-slate-400 font-medium">
                                  {opt.description}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div className={`px-5 py-3.5 rounded-2xl shadow-[0_2px_8px_rgba(0,0,0,0.02)] text-[15px] leading-relaxed transition-all duration-300 border rounded-tl-none ${darkMode
                        ? 'bg-slate-800/40 text-slate-200 border-slate-800/80'
                        : 'bg-white text-slate-800 border-slate-200/50'
                        }`}>
                        <MarkdownRenderer content={msg.content} />
                      </div>
                    );
                  })()}



                  {/* Dynamic Confirmations & Actions */}

                  {msg.ticket_id && (
                    <div className="mt-3.5 flex items-center gap-3.5 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-900/30 text-emerald-800 dark:text-emerald-300 px-4.5 py-3.5 rounded-2xl w-full max-w-sm shadow-sm animate-message-fade">
                      <div className="p-2 bg-emerald-100/50 dark:bg-emerald-900/40 rounded-xl">
                        <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                      </div>
                      <div>
                        <h4 className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 dark:text-emerald-400">Freshservice Dispatch</h4>
                        <p className="text-[13px] font-semibold text-emerald-700 dark:text-emerald-300 mt-0.5">Ticket ID: #{msg.ticket_id}</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Glowing loader */}
          {isLoading && (
            <div className="flex justify-start animate-message-fade">
              <div className="flex gap-4">
                <div className="flex-shrink-0 h-10 w-10 rounded-[14px] bg-white dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-800/80 flex items-center justify-center shadow-sm">
                  <Bot className="h-5 w-5 text-[#6366f1] animate-bounce" />
                </div>
                <div className={`px-5 py-4 rounded-2xl border shadow-sm flex items-center justify-center ${darkMode ? 'bg-slate-800/40 border-slate-800/80' : 'bg-white border-slate-200/60'
                  }`}>
                  <div className="flex space-x-1.5 items-center">
                    <div className="w-2 h-2 bg-[#6366f1] rounded-full animate-bounce" style={{ animationDelay: '0s' }}></div>
                    <div className="w-2 h-2 bg-[#6366f1] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 bg-[#6366f1] rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                    <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 ml-2 animate-pulse">Running workflows...</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>



        {/* Chat Input Bar */}
        <div className="p-8 flex flex-col gap-3">
          {attachment && (() => {
            const isImg = attachment.name.match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i);
            return (
              <div className={`flex items-center justify-between p-3 rounded-2xl border text-sm max-w-md animate-message-fade ${darkMode ? 'bg-slate-900/60 border-slate-800/80' : 'bg-slate-50 border-slate-200/50'}`}>
                <div className="flex items-center gap-3 overflow-hidden">
                  {isImg ? (
                    <div className="w-10 h-10 rounded-lg overflow-hidden border border-slate-200/50 dark:border-slate-800/60 shrink-0">
                      <img src={attachment.data} alt="Preview" className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <FileText className="w-5 h-5 text-indigo-500 shrink-0" />
                  )}
                  <span className="truncate font-medium text-slate-800 dark:text-slate-250">{attachment.name}</span>
                </div>
                <button 
                  type="button" 
                  onClick={() => setAttachment(null)}
                  className="text-xs text-rose-500 hover:text-rose-600 font-bold ml-4 cursor-pointer transition-colors"
                >
                  Remove
                </button>
              </div>
            );
          })()}
          <div className={`relative shadow-[0_8px_32px_rgba(0,0,0,0.03)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.2)] rounded-2xl border flex items-center p-2.5 transition-all duration-500 focus-within:ring-2 focus-within:ring-[#6366f1]/20 focus-within:border-[#6366f1] ${darkMode ? 'bg-slate-800/30 border-slate-800/80' : 'bg-white/80 border-slate-200/60'
            }`}>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-3 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors ml-1 rounded-xl hover:bg-slate-100/50 dark:hover:bg-slate-800/60"
              title="Attach File"
            >
              <Paperclip className="w-5 h-5 transform -rotate-45" />
            </button>
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept="image/*,.pdf,.doc,.docx"
              onChange={handleFileChange}
            />

            <form onSubmit={handleSubmit} className="flex-1 flex items-center">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me anything ..."
                className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 text-[15px] px-4 placeholder-slate-400 dark:placeholder-slate-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="ml-2 bg-gradient-to-tr from-[#6366f1] to-[#8b5cf6] hover:scale-105 active:scale-95 text-white p-3.5 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-[0_4px_16px_rgba(99,102,241,0.3)]"
              >
                <Send className="w-4 h-4 text-white" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
