import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

interface Message {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: any[]
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [session, setSession] = useState('customer:ACCT-001')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim()) return

    const userMessage: Message = {
      role: 'user',
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/chat/message`,
        { message: input },
        {
          headers: {
            'x-session': session,
          },
        }
      )

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.data.reply,
        toolCalls: response.data.tool_calls,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Error communicating with the agent. Please try again.',
      }
      setMessages((prev) => [...prev, errorMessage])
      console.error('Chat error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.sidebar}>
        <h2>ParcelPilot Agent</h2>
        <div style={styles.sessionControl}>
          <label>Session:</label>
          <select
            value={session}
            onChange={(e) => setSession(e.target.value)}
            style={styles.select}
          >
            <option value="customer:ACCT-001">Customer: Northstar</option>
            <option value="customer:ACCT-002">Customer: LumenWorks</option>
            <option value="customer:ACCT-003">Customer: Growth Plan</option>
            <option value="customer:ACCT-004">Customer: Axis Labs</option>
            <option value="staff:support">Staff: Support</option>
            <option value="staff:ops">Staff: Operations</option>
          </select>
        </div>
      </div>

      <div style={styles.chatContainer}>
        <div style={styles.messages}>
          {messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                ...styles.message,
                ...(msg.role === 'user' ? styles.userMessage : styles.assistantMessage),
              }}
            >
              <strong>{msg.role === 'user' ? 'You' : 'Agent'}:</strong>
              <p>{msg.content}</p>
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <details style={styles.toolDetails}>
                  <summary>Tool calls ({msg.toolCalls.length})</summary>
                  <pre>{JSON.stringify(msg.toolCalls, null, 2)}</pre>
                </details>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div style={styles.inputArea}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !loading && sendMessage()}
            placeholder="Ask about orders, tickets, policies..."
            style={styles.input}
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading}
            style={styles.button}
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    height: '100vh',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  } as React.CSSProperties,
  sidebar: {
    width: '250px',
    borderRight: '1px solid #e0e0e0',
    padding: '20px',
    backgroundColor: '#f9f9f9',
  } as React.CSSProperties,
  sessionControl: {
    marginTop: '20px',
  } as React.CSSProperties,
  select: {
    width: '100%',
    marginTop: '8px',
    padding: '8px',
    border: '1px solid #ccc',
    borderRadius: '4px',
  } as React.CSSProperties,
  chatContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  } as React.CSSProperties,
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
    backgroundColor: '#fafafa',
  } as React.CSSProperties,
  message: {
    marginBottom: '16px',
    padding: '12px',
    borderRadius: '8px',
    wordWrap: 'break-word',
  } as React.CSSProperties,
  userMessage: {
    backgroundColor: '#e3f2fd',
    marginLeft: '40px',
  } as React.CSSProperties,
  assistantMessage: {
    backgroundColor: '#f5f5f5',
    marginRight: '40px',
  } as React.CSSProperties,
  toolDetails: {
    marginTop: '8px',
    padding: '8px',
    backgroundColor: 'rgba(0,0,0,0.05)',
    borderRadius: '4px',
    fontSize: '12px',
  } as React.CSSProperties,
  inputArea: {
    display: 'flex',
    gap: '8px',
    padding: '16px',
    borderTop: '1px solid #e0e0e0',
    backgroundColor: '#fff',
  } as React.CSSProperties,
  input: {
    flex: 1,
    padding: '10px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
  } as React.CSSProperties,
  button: {
    padding: '10px 20px',
    backgroundColor: '#2196F3',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
  } as React.CSSProperties,
}
