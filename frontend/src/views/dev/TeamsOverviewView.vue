<!--
  Vista: TeamsOverviewView ("Equipos")

  CONTEXTO: Alloxentric opera como software factory con convenio con
  universidades (DuocUC, UTEM). Cada semestre reparte decenas de proyectos
  entre muchos equipos de estudiantes, y cada equipo suele trabajar un
  conjunto propio de épicas — a veces repartidas entre varias aplicaciones.

  Esta vista agrupa esas épicas por Equipo (Team) para poder ver y evaluar
  el trabajo de cada equipo como una unidad ("mini-proyecto"), sin tener que
  abrir épica por épica ni mantener un Excel aparte. Es exactamente el
  "paso intermedio" que el Team Leader necesitaba: no reemplaza el Builder
  (donde se crean las épicas y se les asigna un equipo), sino que da la
  vista agregada de seguimiento/evaluación a fin de semestre.
-->

<template>
  <div class="flex flex-col min-h-screen bg-[var(--bg-app)]">
    <AppHeader />

    <div class="flex-1 overflow-y-auto">
      <header class="bg-[var(--bg-card)] border-b border-[var(--border-subtle)] px-6 py-5 sticky top-0 z-30">
        <div class="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 class="text-2xl font-bold text-[var(--text-primary)]">{{ t('teamsView.title') }}</h1>
            <p class="text-[var(--text-secondary)] text-sm mt-1">{{ t('teamsView.subtitle') }}</p>
          </div>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg bg-[var(--teal)] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[var(--teal-90)]"
            @click="openCreateModal"
          >
            + {{ t('teamsView.newTeam') }}
          </button>
        </div>
      </header>

      <main class="p-6 space-y-4">
        <div v-if="teamsStore.isLoading && teamsStore.teams.length === 0" class="text-center py-16 text-[var(--text-muted)]">
          {{ t('teamsView.loading') }}
        </div>

        <div v-else-if="teamsStore.teams.length === 0" class="rounded-2xl border border-dashed border-[var(--border-subtle)] bg-[var(--bg-panel)] p-10 text-center text-[var(--text-muted)]">
          {{ t('teamsView.noTeams') }}
        </div>

        <article
          v-for="team in teamsStore.teams"
          :key="team.id"
          class="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] overflow-hidden"
        >
          <div class="flex flex-col gap-3 p-5 md:flex-row md:items-center md:justify-between">
            <div class="min-w-0 flex-1 cursor-pointer" @click="toggleExpand(team.id)">
              <div class="flex items-center gap-2 flex-wrap">
                <h2 class="text-lg font-semibold text-[var(--text-primary)] truncate">{{ team.name }}</h2>
                <span class="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
                  {{ team.epicCount }} {{ t('teamsView.epics') }}
                </span>
                <span
                  v-if="isWeak(team)"
                  class="rounded-full bg-[var(--priority-urg-bg)]/15 px-2 py-0.5 text-[11px] font-semibold text-[var(--priority-urg-bg)]"
                  :title="t('teamsView.weakHint')"
                >
                  ⚠️ {{ t('teamsView.needsReview') }}
                </span>
              </div>
              <p v-if="team.description" class="mt-1 text-sm text-[var(--text-secondary)]">{{ team.description }}</p>

              <div class="mt-3 flex items-center gap-3">
                <div class="h-2 flex-1 max-w-md overflow-hidden rounded-full bg-[var(--border-subtle)]">
                  <div
                    class="h-full rounded-full transition-all"
                    :class="progressBarClass(team.progress)"
                    :style="{ width: `${team.progress}%` }"
                  />
                </div>
                <span class="text-sm font-medium text-[var(--text-secondary)] whitespace-nowrap">
                  {{ team.completedTickets }}/{{ team.totalTickets }} {{ t('teamsView.ticketsDone') }} · {{ team.progress }}%
                </span>
              </div>
            </div>

            <div class="flex items-center gap-2 shrink-0">
              <button
                type="button"
                class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-card)]/10"
                @click="openEditModal(team)"
              >
                {{ t('builderView.edit') }}
              </button>
              <button
                type="button"
                class="rounded-lg border border-[var(--priority-urg-bg)]/60 bg-[var(--priority-urg-bg)] px-3 py-2 text-sm text-white transition hover:bg-[var(--priority-urg-bg)]/80"
                @click="removeTeam(team)"
              >
                {{ t('builderView.delete') }}
              </button>
              <button
                type="button"
                class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] p-2 text-[var(--text-secondary)] transition hover:bg-[var(--bg-card)]/10"
                @click="toggleExpand(team.id)"
                :aria-label="expandedTeamId === team.id ? t('teamsView.collapse') : t('teamsView.expand')"
              >
                <svg class="h-4 w-4 transition-transform" :class="expandedTeamId === team.id ? 'rotate-180' : ''" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
          </div>

          <div v-if="expandedTeamId === team.id" class="border-t border-[var(--border-subtle)] bg-[var(--bg-panel)]/40 p-5">
            <div v-if="detailLoading" class="text-sm text-[var(--text-muted)]">{{ t('teamsView.loading') }}</div>
            <div v-else-if="!teamDetail || teamDetail.id !== team.id" class="text-sm text-[var(--text-muted)]">—</div>
            <div v-else-if="teamDetail.epics.length === 0" class="text-sm text-[var(--text-muted)]">{{ t('teamsView.noEpicsForTeam') }}</div>
            <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <div
                v-for="epic in teamDetail.epics"
                :key="epic.id"
                class="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4"
              >
                <p class="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">{{ epic.applicationName || '—' }}</p>
                <h3 class="mt-0.5 font-semibold text-[var(--text-primary)] truncate">{{ epic.title }}</h3>

                <div class="mt-2 flex items-center gap-2">
                  <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--border-subtle)]">
                    <div class="h-full rounded-full bg-[var(--teal)]" :style="{ width: `${epic.progress}%` }" />
                  </div>
                  <span class="text-xs text-[var(--text-muted)] whitespace-nowrap">{{ epic.completedTickets }}/{{ epic.totalTickets }}</span>
                </div>

                <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                  <span v-for="(count, status) in ticketStatusBreakdown(epic)" :key="status" v-show="count > 0"
                    class="rounded-full px-2 py-0.5" :class="statusBadgeClass(status)">
                    {{ count }} {{ statusLabel(status) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </article>
      </main>
    </div>

    <!-- Modal crear/editar equipo -->
    <Teleport to="body">
      <div v-if="showModal" class="fixed inset-0 z-[100] flex items-center justify-center bg-[var(--bg-app)]/80 px-4 backdrop-blur-sm" @click.self="closeModal">
        <div class="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-app)] p-6 shadow-2xl">
          <h3 class="text-lg font-semibold text-[var(--text-primary)]">
            {{ editingTeamId ? t('teamsView.editTeam') : t('teamsView.newTeam') }}
          </h3>
          <form class="mt-4 space-y-3" @submit.prevent="saveTeam">
            <div>
              <label class="mb-1 block text-sm text-[var(--text-secondary)]">{{ t('teamsView.nameLabel') }}</label>
              <input
                v-model="teamForm.name"
                type="text"
                autofocus
                class="w-full rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-4 py-2.5 text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--teal)] focus:outline-none"
                :placeholder="t('teamsView.namePlaceholder')"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm text-[var(--text-secondary)]">{{ t('builderView.formDescription') }}</label>
              <textarea
                v-model="teamForm.description"
                rows="3"
                class="w-full rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-4 py-2.5 text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--teal)] focus:outline-none"
                :placeholder="t('teamsView.descPlaceholder')"
              />
            </div>
            <p v-if="modalError" class="rounded-lg border border-[var(--priority-urg-bg)]/30 bg-[var(--priority-urg-bg)]/10 px-3 py-2 text-sm text-[var(--priority-urg-bg)]">
              {{ modalError }}
            </p>
            <div class="flex gap-3 pt-2">
              <button type="submit" :disabled="saving" class="flex-1 rounded-xl bg-[var(--teal)] px-4 py-2.5 font-semibold text-white transition hover:bg-[var(--teal-90)] disabled:opacity-50">
                {{ saving ? t('builderView.saving') : t('common.save') }}
              </button>
              <button type="button" class="flex-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-4 py-2.5 font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-card)]/10" @click="closeModal">
                {{ t('common.cancel') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useTeamsStore } from '@/stores'
import { useDialogStore } from '@/stores/dialog'
import type { Team, TeamDetail } from '@/types'

const { t } = useI18n()
const teamsStore = useTeamsStore()
const dialogStore = useDialogStore()

const expandedTeamId = ref<string | null>(null)
const teamDetail = ref<TeamDetail | null>(null)
const detailLoading = ref(false)

const showModal = ref(false)
const editingTeamId = ref<string | null>(null)
const saving = ref(false)
const modalError = ref('')
const teamForm = reactive({ name: '', description: '' })

// Un equipo con progreso bajo (menos de un tercio) es candidato a revisar
// con prioridad a fin de semestre. Umbral simple e intencionalmente
// conservador — es una señal visual, no una nota automática.
const WEAK_THRESHOLD = 33
const isWeak = (team: Team) => team.totalTickets > 0 && team.progress < WEAK_THRESHOLD

const progressBarClass = (progress: number) => {
  if (progress >= 66) return 'bg-[var(--status-done-bg)]'
  if (progress >= 33) return 'bg-[var(--priority-med-bg)]'
  return 'bg-[var(--priority-urg-bg)]'
}

const STATUS_KEYS = ['TODO', 'IN_PROGRESS', 'BLOCKED', 'BLOCKED_QUESTION', 'COMPLETED'] as const

const ticketStatusBreakdown = (epic: any): Record<string, number> => {
  const counts: Record<string, number> = { TODO: 0, IN_PROGRESS: 0, BLOCKED: 0, BLOCKED_QUESTION: 0, COMPLETED: 0 }
  for (const ticket of epic.tickets || []) {
    const status = String(ticket.status || 'TODO').toUpperCase()
    if (status === 'DONE') counts.COMPLETED++
    else if (status in counts) counts[status]++
  }
  return counts
}

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    TODO: t('teamsView.statusTodo'),
    IN_PROGRESS: t('teamsView.statusInProgress'),
    BLOCKED: t('teamsView.statusBlocked'),
    BLOCKED_QUESTION: t('teamsView.statusBlocked'),
    COMPLETED: t('teamsView.statusCompleted'),
  }
  return labels[status] || status
}

const statusBadgeClass = (status: string) => {
  const classes: Record<string, string> = {
    TODO: 'bg-[var(--bg-panel)] text-[var(--text-secondary)]',
    IN_PROGRESS: 'bg-[var(--teal)]/15 text-[var(--teal)]',
    BLOCKED: 'bg-[var(--priority-urg-bg)]/15 text-[var(--priority-urg-bg)]',
    BLOCKED_QUESTION: 'bg-[var(--priority-urg-bg)]/15 text-[var(--priority-urg-bg)]',
    COMPLETED: 'bg-[var(--status-done-bg)]/15 text-[var(--status-done-bg)]',
  }
  return classes[status] || 'bg-[var(--bg-panel)] text-[var(--text-secondary)]'
}

const toggleExpand = async (teamId: string) => {
  if (expandedTeamId.value === teamId) {
    expandedTeamId.value = null
    return
  }
  expandedTeamId.value = teamId
  detailLoading.value = true
  try {
    teamDetail.value = await teamsStore.getDetail(teamId)
  } catch (error) {
    console.error('Error al cargar detalle del equipo:', error)
  } finally {
    detailLoading.value = false
  }
}

const openCreateModal = () => {
  editingTeamId.value = null
  teamForm.name = ''
  teamForm.description = ''
  modalError.value = ''
  showModal.value = true
}

const openEditModal = (team: Team) => {
  editingTeamId.value = team.id
  teamForm.name = team.name
  teamForm.description = team.description || ''
  modalError.value = ''
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
}

const saveTeam = async () => {
  if (!teamForm.name.trim()) {
    modalError.value = t('teamsView.nameRequired')
    return
  }
  saving.value = true
  modalError.value = ''
  try {
    if (editingTeamId.value) {
      await teamsStore.update(editingTeamId.value, { name: teamForm.name, description: teamForm.description })
    } else {
      await teamsStore.create({ name: teamForm.name, description: teamForm.description })
    }
    closeModal()
  } catch (error: any) {
    modalError.value = error?.response?.data?.detail || (error instanceof Error ? error.message : 'Error al guardar el equipo')
  } finally {
    saving.value = false
  }
}

const removeTeam = async (team: Team) => {
  const confirmed = await dialogStore.confirm(
    t('teamsView.confirmDelete', { name: team.name }) as string
  )
  if (!confirmed) return
  try {
    await teamsStore.remove(team.id)
    if (expandedTeamId.value === team.id) expandedTeamId.value = null
  } catch (error) {
    console.error('Error al eliminar equipo:', error)
  }
}

onMounted(() => {
  teamsStore.fetchAll()
})
</script>
