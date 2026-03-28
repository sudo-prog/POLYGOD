import { useEffect, useRef, useCallback } from 'react'
import { useMarketStore } from '../stores/marketStore'

export interface RAGGodData {
    paper_pnl: number
    paper_stats: {
        total_pnl: number
        current_capital: number
        return_pct: number
        open_positions: number
        total_trades: number
        win_rate: number
        recent_pnls: number[]
    }
    mode: number
    mode_name: string
    whale_alert: string
    timestamp: string
}

export interface RAGGodState {
    isConnected: boolean
    data: RAGGodData | null
    lastAlert: string | null
    reconnectAttempts: number
}

const WS_URL = 'ws://localhost:8000/ws/rag-god'
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY = 3000

export function useRAGGodWS() {
    const wsRef = useRef<WebSocket | null>(null)
    const reconnectTimeoutRef = useRef<number | null>(null)
    const reconnectAttemptsRef = useRef(0)

    const { setRagGodState, ragGodState } = useMarketStore()

    const connect = useCallback(() => {
        // Don't connect if already connected
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return
        }

        try {
            console.log('[RAG_GOD] Connecting to WebSocket...')

            const ws = new WebSocket(WS_URL)
            wsRef.current = ws

            ws.onopen = () => {
                console.log('[RAG_GOD] WebSocket connected')
                reconnectAttemptsRef.current = 0

                setRagGodState({
                    isConnected: true,
                    reconnectAttempts: 0,
                    data: ragGodState.data,
                    lastAlert: ragGodState.lastAlert
                })
            }

            ws.onmessage = (event) => {
                try {
                    const data: RAGGodData = JSON.parse(event.data)
                    console.log('[RAG_GOD] Received:', data)

                    setRagGodState({
                        isConnected: true,
                        data: data,
                        lastAlert: data.whale_alert || ragGodState.lastAlert,
                        reconnectAttempts: reconnectAttemptsRef.current
                    })
                } catch (error) {
                    console.error('[RAG_GOD] Failed to parse message:', error)
                }
            }

            ws.onerror = (error) => {
                console.error('[RAG_GOD] WebSocket error:', error)
            }

            ws.onclose = (event) => {
                console.log('[RAG_GOD] WebSocket closed:', event.code, event.reason)

                wsRef.current = null

                setRagGodState({
                    isConnected: false,
                    data: ragGodState.data,
                    lastAlert: ragGodState.lastAlert,
                    reconnectAttempts: reconnectAttemptsRef.current
                })

                // Attempt to reconnect
                if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
                    reconnectAttemptsRef.current++
                    console.log(`[RAG_GOD] Reconnecting in ${RECONNECT_DELAY}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`)

                    reconnectTimeoutRef.current = window.setTimeout(() => {
                        connect()
                    }, RECONNECT_DELAY)
                } else {
                    console.error('[RAG_GOD] Max reconnect attempts reached')
                }
            }
        } catch (error) {
            console.error('[RAG_GOD] Failed to create WebSocket:', error)
        }
    }, [setRagGodState, ragGodState.data, ragGodState.lastAlert])

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
        }

        if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
        }

        reconnectAttemptsRef.current = 0
    }, [])

    const reconnect = useCallback(() => {
        disconnect()
        reconnectAttemptsRef.current = 0
        connect()
    }, [connect, disconnect])

    // Connect on mount, disconnect on unmount
    useEffect(() => {
        connect()

        return () => {
            disconnect()
        }
    }, [connect, disconnect])

    return {
        isConnected: ragGodState.isConnected,
        data: ragGodState.data,
        lastAlert: ragGodState.lastAlert,
        reconnectAttempts: ragGodState.reconnectAttempts,
        reconnect,
        disconnect
    }
}

export default useRAGGodWS
