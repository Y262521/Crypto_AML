import { useEffect } from 'react';

export const useRealtime = (onNewTransaction) => {
    useEffect(() => {
        if (!import.meta.env.VITE_INFURA_KEY) return; // skip if no key configured

        const ws = new WebSocket(`wss://mainnet.infura.io/ws/v3/${import.meta.env.VITE_INFURA_KEY}`);

        ws.onopen = () => {
            ws.send(JSON.stringify({
                jsonrpc: "2.0",
                id: 1,
                method: "eth_subscribe",
                params: ["newPendingTransactions"]
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.params && data.params.result) {
                onNewTransaction(data.params.result);
            }
        };

        return () => ws.close();
    }, [onNewTransaction]);
};
