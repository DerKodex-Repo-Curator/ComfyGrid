<script lang="ts">
  import { Workflow } from '@lucide/svelte';
  import AppMenu from '@/components/common/AppMenu.svelte';
  import { t } from '@/i18n/i18n';
  import { appState } from '@/states/app-state.svelte';
  import type { WorkflowTabItem } from '@/states/comfyui-bridge.svelte';
  import type { MenuEntry } from '@/types/menu';

  const uiState = appState.uiState;

  let workflowTabs = $state<WorkflowTabItem[]>([]);

  function refreshWorkflowTabs() {
    if (appState.bridge) {
      workflowTabs = appState.bridge.getWorkflowTabs();
    }
  }

  function handleSelectTab(item: WorkflowTabItem) {
    if (item.selected) return;

    const app = appState.comfyUiState.app;
    if (!app) return;

    item.tab.click();
    if (uiState.activePageId !== 'grid' && uiState.activePageId !== 'comfyui') {
      uiState.needRefresh = true;
    }
  }
  const items = $derived(
    workflowTabs.map((item, index): MenuEntry => ({
      id: `${item.label}-${index}`,
      kind: 'action',
      label: item.label,
      selected: item.selected,
      onSelect: () => handleSelectTab(item),
    })),
  );
</script>

<AppMenu
  {items}
  onOpenChange={(open) => {
    if (open) refreshWorkflowTabs();
  }}
>
  {#snippet trigger({ props })}
    <button
      {...props}
      class="dropdown-toggle btn btn-outline-secondary d-flex justify-content-center align-items-center p-1"
      type="button"
      aria-label={$t('menu.workflows')}
      style="width: 2.2rem; height: 2.2rem;"
      ><Workflow size={18} />
    </button>
  {/snippet}
</AppMenu>

<style lang="scss">
  .dropdown-toggle::after {
    display: none;
  }
</style>
