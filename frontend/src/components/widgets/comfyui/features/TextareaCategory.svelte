<script lang="ts">
  import { Check, Languages, Loader2, TriangleAlert, X } from '@lucide/svelte';
  import AppMenu from '@/components/common/AppMenu.svelte';
  import { t } from '@/i18n/i18n';
  import {
    TEXT_CATEGORIES,
    getTextCategory,
    setTextCategory,
  } from '@/services/text-widget-service';
  import { translationManager } from '@/services/translation-service.svelte';
  import { appState } from '@/states/app-state.svelte';
  import type { ComfyGridWidget } from '@/states/model-state.svelte';
  import type { MenuEntry } from '@/types/menu';

  let { widget, onManualTranslate }: { widget: ComfyGridWidget; onManualTranslate?: () => void } =
    $props();

  const workspaceState = appState.workspaceState;
  const optionState = appState.optionState;

  const layout = $derived(workspaceState.layout);
  const isTranslate = $derived(layout.isTranslateWidget(widget.id));
  const isManual = $derived(
    (optionState.get('ComfyGrid.ollama.translate_timing') ?? 'on_generate') === 'manual',
  );

  const category = $derived(getTextCategory(widget));
  const textCategoryLabel = $derived($t(`widget.select.${category}.title`));
  const items = $derived(
    TEXT_CATEGORIES.map((value): MenuEntry => ({
      id: value,
      kind: 'action',
      label: $t(`widget.select.${value}.title`),
      selected: category === value,
      onSelect: () => setTextCategory(widget, value),
    })),
  );
</script>

<div class="d-inline-flex align-items-center">
  <AppMenu {items} side="right">
    {#snippet trigger({ props })}
      <button
        {...props}
        type="button"
        class="nav-link dropdown-toggle text-capitalize me-2 border-0 bg-transparent"
      >
        {textCategoryLabel}
      </button>
    {/snippet}
  </AppMenu>
  {#if widget.isTranslating}
    <span class="badge text-bg-primary ms-2 fs-7 d-inline-flex align-items-center gap-1">
      <Loader2 size={14} class="spin" />
      {$t('widget.translate.indicator')}
      <button
        type="button"
        class="btn text-white p-0 border-0 d-inline-flex align-items-center justify-content-center"
        title={$t('widget.translate.cancel_hint')}
        aria-label={$t('widget.translate.cancel_hint')}
        onclick={() => translationManager.cancelAll()}
      >
        <X size={14} />
      </button>
    </span>
  {:else if isTranslate && isManual && widget.isDirty}
    <button
      class="badge btn btn-primary ms-2 px-2 d-inline-flex align-items-center gap-1"
      onclick={() => {
        if (onManualTranslate) {
          onManualTranslate();
        } else if (widget.triggerTranslation) {
          widget.triggerTranslation();
        }
      }}
    >
      <Languages size={14} />
      {$t('widget.translate.manual_button')}
    </button>
  {:else if isTranslate && widget.translationFailed}
    <span class="badge text-bg-danger ms-2 fs-7 d-inline-flex align-items-center gap-1">
      <TriangleAlert size={14} />
      {$t('widget.translate.failed')}
    </span>
  {:else if isTranslate && !widget.isDirty && widget.rawValue && widget.rawValue.trim() !== ''}
    <span class="badge text-bg-success ms-2 fs-7 d-inline-flex align-items-center gap-1">
      <Check size={14} />
      {$t('widget.translate.completed')}
    </span>
  {/if}
</div>
