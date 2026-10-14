import { ComfyUiApiHook } from '@/bridge/comfyui-api-hook';
import { NodeDuplicationError, duplicateNodeAfter } from '@/bridge/node-duplication';
import { nodeQueueManager } from '@/bridge/node-queue-manager';
import { executionManager } from '@/managers/execution-manager';
import { translationManager } from '@/services/translation-service.svelte';
import type { ComfyGraph, ComfyNode } from '@/types/comfy-model';
import logger from '@/utils/logger';
import { appState } from './app-state.svelte';

/**
 *
 * @param graph
 */
async function waitOnDrawBackgroundAll(graph: ComfyGraph) {
    for (const node of graph.nodes) {
        try {
            node.onDrawBackground?.();
        } catch (error) {
            logger.error('Error in onDrawBackground for node', node, error);
        }
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
}

export type WorkflowTabItem = {
    label: string;
    tab: HTMLButtonElement;
    selected: boolean;
};

export class ComfyUiBridge {
    static #instance: ComfyUiBridge;

    readonly #app = $derived(appState.comfyUiState.app);

    static getInstance() {
        if (!this.#instance) {
            this.#instance = new this();
        }
        return this.#instance;
    }

    private constructor() {}

    duplicateNode(payload: { nodeId: string }): ComfyNode {
        const source = appState.workspaceState.getRealNode(payload.nodeId)?.comfyNode;
        if (!source) throw new NodeDuplicationError('unavailable');
        return duplicateNodeAfter(source);
    }

    toggleNodeCollapsed(payload: { nodeId: string }): void {
        const node = appState.workspaceState.getRealNode(payload.nodeId);
        const source = node?.comfyNode;
        const graph = source?.graph;
        if (!node || !source || !graph || graph.getNodeById(source.id) !== source) throw new Error('Node is no longer available');
        graph.beforeChange(source);
        try {
            source.collapse(false);
            node.collapsed = Boolean(source.flags.collapsed ?? source.collapsed);
        } finally {
            graph.afterChange(source);
            graph.setDirtyCanvas(true, true);
        }
    }

    deleteNode(payload: { nodeId: string }): void {
        const source = appState.workspaceState.getRealNode(payload.nodeId)?.comfyNode;
        const graph = source?.graph;
        if (!source || !graph || graph.getNodeById(source.id) !== source) throw new Error('Node is no longer available');
        if (source.block_delete || source.ignore_remove) throw new Error('Node cannot be deleted');
        graph.beforeChange(source);
        try {
            // Match ComfyUI's canvas deletion; let the native method decide how to reconnect.
            source.connectInputToOutput?.();
            graph.remove(source);
            if (graph.getNodeById(source.id) === source) throw new Error('Node cannot be deleted');
        } finally {
            graph.afterChange(source);
            graph.setDirtyCanvas(true, true);
        }
    }

    /**
     * Get list of all workflow tab items in ComfyUI.
     */
    getWorkflowTabs(): WorkflowTabItem[] {
        const doc = appState.comfyUiState.window?.document || appState.comfyUiState.iframe?.contentDocument || document;
        const buttons = doc.querySelectorAll<HTMLButtonElement>('.workflow-tabs > button');
        const items: WorkflowTabItem[] = [];

        buttons.forEach((btn) => {
            const labelEl = btn.querySelector('.workflow-label');
            const label = labelEl?.textContent?.trim() || 'Untitled';
            const selected = btn.classList.contains('p-togglebutton-checked');
            items.push({ label, tab: btn, selected });
        });

        return items;
    }

    async getWorkflow(): Promise<{
        graphId: string;
        name: string;
        nodes: ComfyNode[];
    }> {
        const app = appState.comfyUiState.app;
        const nodes: ComfyNode[] = app.rootGraph.nodes;

        await waitOnDrawBackgroundAll(app.rootGraph);

        ComfyUiApiHook.hookForGraphSetDirtyCanvas(app.rootGraph);
        for (const topNode of app.rootGraph.nodes) {
            ComfyUiApiHook.hookForWidgetCallback(topNode);
        }

        const tabs = this.getWorkflowTabs();
        const activeTab = tabs.find((t) => t.selected);
        const title = activeTab?.label || 'Untitled';

        return {
            graphId: app.rootGraph.id,
            name: title,
            nodes,
        };
    }

    /**
     * Handle queue prompt command from ComfyGrid
     * @param batchCount - Number of batches to queue
     */
    async queuePrompt(batchCount: number): Promise<void> {
        const finishRequest = executionManager.beginExecutionRequest();
        let signal: AbortSignal | undefined;
        let isWaiting = false;
        try {
            translationManager.registerPendingTranslations();
            signal = translationManager.cancellationSignal;
            isWaiting = translationManager.isTranslating || translationManager.hasPendingTasks;
            if (isWaiting) translationManager.incrementPendingQueue(batchCount);
            if (!(await translationManager.waitForAllTranslations(signal)) || signal.aborted) return;
            await this.#app.queuePrompt(0, batchCount);
        } finally {
            if (isWaiting && !signal?.aborted) {
                translationManager.decrementPendingQueue(batchCount);
            }
            finishRequest();
        }
    }

    async nodeQueue(payload: { nodeId: string }): Promise<void> {
        const finishRequest = executionManager.beginExecutionRequest();
        let signal: AbortSignal | undefined;
        let isWaiting = false;
        try {
            translationManager.registerPendingTranslations();
            signal = translationManager.cancellationSignal;
            isWaiting = translationManager.isTranslating || translationManager.hasPendingTasks;
            if (isWaiting) translationManager.incrementPendingQueue(1);
            if (!(await translationManager.waitForAllTranslations(signal)) || signal.aborted) return;
            const { nodeId } = payload;
            await nodeQueueManager.queueOutputNodes(this.#app, nodeId);
        } finally {
            if (isWaiting && !signal?.aborted) {
                translationManager.decrementPendingQueue(1);
            }
            finishRequest();
        }
    }

    /**
     * Handle load workflow command from ComfyGrid
     * @param e - Message event containing workflow JSON string
     * @param payload
     * @param payload.filename
     * @param payload.json
     */
    async loadWorkflow(payload: { filename: string; json: unknown }): Promise<{ success: boolean; error?: string }> {
        const { filename, json } = payload;
        try {
            await this.#app.loadGraphData(json, true, true, filename, {
                showMissingNodesDialog: true,
                showMissingModelsDialog: true,
            });
            return { success: true };
        } catch (error) {
            logger.error('Failed to load workflow', error);
            return {
                success: false,
                error: error instanceof Error ? error.message : String(error),
            };
        }
    }
}
