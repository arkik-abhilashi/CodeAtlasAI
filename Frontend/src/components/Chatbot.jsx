import { useState } from "react";

const prompts = [
  "How should I understand a new codebase?",
  "Explain architecture mapping",
  "What can Atlas help me with?",
];

const firstMessage = {
  role: "assistant",
  text: "Hi, I'm Atlas. I can help you understand code, architecture, and dependencies. This preview is in demo mode, so I don't have access to a repository yet.",
};

function demoAnswer(question) {
  const q = question.toLowerCase();

  if (q.includes("architecture") || q.includes("structure")) {
    return "A good starting point is to identify the app entry point, UI components, service/API layer, and shared utilities. Then trace imports between those parts to build a map of the system. Once repository access is connected, Atlas can ground this analysis in your actual files.";
  }

  if (q.includes("depend")) {
    return "Dependencies describe which parts of a project rely on other parts. Start by tracing imports from the entry point, then group the results into UI, business logic, services, and utilities. A repository connection would let Atlas analyze your real dependency graph.";
  }

  if (q.includes("codebase") || q.includes("new project")) {
    return "For a new codebase, start with package scripts and the application entry point. Follow the render path, identify API calls and data models, then inspect shared utilities. Atlas is currently using sample responses; connecting a repository and AI backend would make the answers project-specific.";
  }

  return "Atlas is currently a UI prototype with sample replies, not a live AI service. Share a code snippet or a question about software architecture and I can still help; connecting your backend will enable real AI responses inside this interface.";
}

export default function Chatbot() {
  const [messages, setMessages] = useState([firstMessage]);
  const [value, setValue] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  function sendMessage(text = value) {
    const message = text.trim();
    if (!message || isThinking) return;

    setMessages((old) => [...old, { role: "user", text: message }]);
    setValue("");
    setIsThinking(true);

    // Replace this demo response with a POST request to your backend when ready.
    window.setTimeout(() => {
      setMessages((old) => [...old, { role: "assistant", text: demoAnswer(message) }]);
      setIsThinking(false);
    }, 500);
  }

  function submit(event) {
    event.preventDefault();
    sendMessage();
  }

  return (
    <section className="ca-chat-section" id="assistant">
      <div className="ca-section__heading ca-chat-heading">
        <div>
          <p className="ca-kicker">MEET YOUR DEVELOPER COMPANION</p>
          <h2>Ask <span className="ca-gradient-text">Atlas.</span></h2>
        </div>
        <p>Start with a question. Connect a repository when you're ready to explore real project context.</p>
      </div>

      <div className="ca-chat">
        <header className="ca-chat__header">
          <div className="ca-chat__identity">
            <span className="ca-chat__avatar">✳</span>
            <div><strong>Atlas AI</strong><small><span className="ca-status-dot" /> Ready to help</small></div>
          </div>
          <span className="ca-demo-badge">PREVIEW MODE</span>
        </header>

        <div className="ca-chat__context">
          <span aria-hidden="true">▤</span>
          <div><strong>Project context</strong><small>No repository connected</small></div>
          <span className="ca-context-note">Connect later</span>
        </div>

        <div className="ca-chat__messages" aria-live="polite">
          {messages.map((message, index) => (
            <div className={`ca-message ca-message--${message.role}`} key={`${message.role}-${index}`}>
              {message.role === "assistant" && <span className="ca-message__avatar">✳</span>}
              <p>{message.text}</p>
            </div>
          ))}
          {isThinking && (
            <div className="ca-message ca-message--assistant">
              <span className="ca-message__avatar">✳</span>
              <p className="ca-typing"><i /><i /><i /></p>
            </div>
          )}
        </div>

        {messages.length === 1 && (
          <div className="ca-chat__prompts">
            {prompts.map((prompt) => (
              <button type="button" key={prompt} onClick={() => sendMessage(prompt)}>
                <span aria-hidden="true">↗</span>{prompt}
              </button>
            ))}
          </div>
        )}

        <form className="ca-chat__composer" onSubmit={submit}>
          <textarea
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask Atlas about code, architecture, or dependencies..."
            aria-label="Message Atlas"
            rows={2}
          />
          <div className="ca-chat__composer-footer">
            <span>Enter to send · Shift + Enter for a new line</span>
            <button type="submit" disabled={!value.trim() || isThinking} aria-label="Send message">↑</button>
          </div>
        </form>
        <p className="ca-chat__disclaimer">Demo responses only — connect an AI backend for live assistance.</p>
      </div>
    </section>
  );
}
