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
                v-if="isAdmin"
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

          <div v-if="expandedTeamId === team.id" class="border-t border-[var(--border-subtle)] bg-[var(--bg-panel)]/40 p-5 space-y-6">
            <div v-if="detailLoading" class="text-sm text-[var(--text-muted)]">{{ t('teamsView.loading') }}</div>
            <template v-else-if="teamDetail && teamDetail.id === team.id">

              <!-- ============================================================ -->
              <!-- INTEGRANTES -->
              <!-- ============================================================ -->
              <section>
                <h4 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">{{ t('teamsView.members') }}</h4>

                <div v-if="teamDetail.members.length === 0" class="mt-2 text-sm text-[var(--text-muted)]">
                  {{ t('teamsView.noMembers') }}
                </div>
                <div v-else class="mt-2 flex flex-wrap gap-2">
                  <div
                    v-for="member in teamDetail.members"
                    :key="member.id"
                    class="flex items-center gap-2 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-card)] py-1.5 pl-3 pr-2 text-sm"
                  >
                    <span :title="member.userId ? t('teamsView.linkedAccountHint') : undefined" class="text-[var(--text-primary)]">
                      {{ member.userId ? '🔗' : '' }} {{ member.name }}
                    </span>
                    <span v-if="member.email" class="text-xs text-[var(--text-muted)]">{{ member.email }}</span>
                    <button
                      type="button"
                      class="rounded-full p-0.5 text-[var(--text-muted)] hover:bg-[var(--priority-urg-bg)]/15 hover:text-[var(--priority-urg-bg)]"
                      :aria-label="t('teamsView.removeMember')"
                      @click="removeMember(team.id, member)"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                <!-- Formulario para agregar integrante -->
                <div v-if="addingMemberFor === team.id" class="mt-3 rounded-xl border border-[var(--teal)]/40 bg-[var(--bg-card)] p-3 space-y-2">
                  <div class="flex gap-1 text-xs">
                    <button
                      type="button"
                      class="rounded-lg px-2.5 py-1 font-medium transition"
                      :class="memberMode === 'loose' ? 'bg-[var(--teal)] text-white' : 'bg-[var(--bg-panel)] text-[var(--text-secondary)]'"
                      @click="memberMode = 'loose'"
                    >
                      {{ t('teamsView.memberModeLoose') }}
                    </button>
                    <button
                      type="button"
                      class="rounded-lg px-2.5 py-1 font-medium transition"
                      :class="memberMode === 'linked' ? 'bg-[var(--teal)] text-white' : 'bg-[var(--bg-panel)] text-[var(--text-secondary)]'"
                      @click="memberMode = 'linked'; loadSystemUsers()"
                    >
                      {{ t('teamsView.memberModeLinked') }}
                    </button>
                  </div>

                  <template v-if="memberMode === 'loose'">
                    <input
                      v-model="newMemberName"
                      type="text"
                      :placeholder="t('teamsView.memberNamePlaceholder')"
                      class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--teal)] focus:outline-none"
                    />
                    <input
                      v-model="newMemberEmail"
                      type="email"
                      :placeholder="t('teamsView.memberEmailPlaceholder')"
                      class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--teal)] focus:outline-none"
                    />
                  </template>
                  <template v-else>
                    <select
                      v-model="newMemberUserId"
                      class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--teal)] focus:outline-none"
                    >
                      <option value="">{{ t('teamsView.selectUser') }}</option>
                      <option v-for="u in systemUsers" :key="u.id" :value="u.id">{{ u.fullName }} ({{ u.role }})</option>
                    </select>
                    <p class="text-xs text-[var(--text-muted)]">{{ t('teamsView.linkedAccountNote') }}</p>
                  </template>

                  <p v-if="memberError" class="text-xs text-[var(--priority-urg-bg)]">{{ memberError }}</p>

                  <div class="flex gap-2 pt-1">
                    <button type="button" :disabled="savingMember" class="rounded-lg bg-[var(--teal)] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[var(--teal-90)] disabled:opacity-50" @click="addMember(team.id)">
                      {{ savingMember ? t('builderView.saving') : t('common.save') }}
                    </button>
                    <button type="button" class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-1.5 text-xs text-[var(--text-secondary)]" @click="cancelAddMember">
                      {{ t('common.cancel') }}
                    </button>
                  </div>
                </div>
                <button
                  v-else
                  type="button"
                  class="mt-3 rounded-lg border border-dashed border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition hover:border-[var(--teal)] hover:text-[var(--teal)]"
                  @click="addingMemberFor = team.id; memberMode = 'loose'; newMemberName = ''; newMemberEmail = ''; newMemberUserId = ''; memberError = ''"
                >
                  + {{ t('teamsView.addMember') }}
                </button>
              </section>

              <!-- ============================================================ -->
              <!-- ÉPICAS -->
              <!-- ============================================================ -->
              <section>
                <h4 class="text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">{{ t('teamsView.epicsSection') }}</h4>

                <div v-if="teamDetail.epics.length === 0" class="mt-2 text-sm text-[var(--text-muted)]">{{ t('teamsView.noEpicsForTeam') }}</div>
                <div v-else class="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
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

                <!-- Formulario para vincular/crear épica -->
                <div v-if="addingEpicFor === team.id" class="mt-3 rounded-xl border border-[var(--teal)]/40 bg-[var(--bg-card)] p-3 space-y-2">
                  <select
                    v-model="epicFormAppId"
                    class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--teal)] focus:outline-none"
                    @change="loadAppEpics"
                  >
                    <option value="">{{ t('teamsView.selectProject') }}</option>
                    <option v-for="app in applications" :key="app.id" :value="app.id">{{ app.name }}</option>
                  </select>

                  <template v-if="epicFormAppId">
                    <div class="flex gap-1 text-xs">
                      <button type="button" class="rounded-lg px-2.5 py-1 font-medium transition"
                        :class="epicMode === 'existing' ? 'bg-[var(--teal)] text-white' : 'bg-[var(--bg-panel)] text-[var(--text-secondary)]'"
                        @click="epicMode = 'existing'">
                        {{ t('teamsView.epicModeExisting') }}
                      </button>
                      <button type="button" class="rounded-lg px-2.5 py-1 font-medium transition"
                        :class="epicMode === 'new' ? 'bg-[var(--teal)] text-white' : 'bg-[var(--bg-panel)] text-[var(--text-secondary)]'"
                        @click="epicMode = 'new'">
                        {{ t('teamsView.epicModeNew') }}
                      </button>
                    </div>

                    <template v-if="epicMode === 'existing'">
                      <select
                        v-model="epicFormEpicId"
                        class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--teal)] focus:outline-none"
                      >
                        <option value="">{{ t('teamsView.selectEpic') }}</option>
                        <option v-for="e in appEpics" :key="e.id" :value="e.id">
                          {{ e.title }}{{ e.teamName ? ` — ${t('teamsView.currentlyIn')} ${e.teamName}` : '' }}
                        </option>
                      </select>
                    </template>
                    <template v-else>
                      <input
                        v-model="newEpicTitle"
                        type="text"
                        :placeholder="t('builderView.epicTitlePlaceholder')"
                        class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--teal)] focus:outline-none"
                      />
                    </template>
                  </template>

                  <p v-if="epicError" class="text-xs text-[var(--priority-urg-bg)]">{{ epicError }}</p>

                  <div class="flex gap-2 pt-1">
                    <button type="button" :disabled="savingEpic" class="rounded-lg bg-[var(--teal)] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[var(--teal-90)] disabled:opacity-50" @click="linkEpic(team.id)">
                      {{ savingEpic ? t('builderView.saving') : t('common.save') }}
                    </button>
                    <button type="button" class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-panel)] px-3 py-1.5 text-xs text-[var(--text-secondary)]" @click="cancelAddEpic">
                      {{ t('common.cancel') }}
                    </button>
                  </div>
                </div>
                <button
                  v-else
                  type="button"
                  class="mt-3 rounded-lg border border-dashed border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition hover:border-[var(--teal)] hover:text-[var(--teal)]"
                  @click="startAddEpic(team.id)"
                >
                  + {{ t('teamsView.linkEpic') }}
                </button>
              </section>
            </template>
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
import { ref, onMounted, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useTeamsStore, useApplicationsStore, useAuthStore } from '@/stores'
import { useDialogStore } from '@/stores/dialog'
import { api } from '@/services/api'
import type { Team, TeamDetail, TeamMember, User, Application, Epic } from '@/types'

const { t } = useI18n()
const teamsStore = useTeamsStore()
const applicationsStore = useApplicationsStore()
const dialogStore = useDialogStore()
const authStore = useAuthStore()
// Deleting a team grouping is ADMIN-only on the backend (docs/RBAC.md)
const isAdmin = computed(() => authStore.user?.role === 'ADMIN')

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

// =====================================================================
// INTEGRANTES
// =====================================================================

const addingMemberFor = ref<string | null>(null)
const memberMode = ref<'loose' | 'linked'>('loose')
const newMemberName = ref('')
const newMemberEmail = ref('')
const newMemberUserId = ref('')
const memberError = ref('')
const savingMember = ref(false)
const systemUsers = ref<User[]>([])

const loadSystemUsers = async () => {
  if (systemUsers.value.length > 0) return
  try {
    systemUsers.value = await api.team.list()
  } catch (error) {
    console.error('Error al cargar usuarios del sistema:', error)
  }
}

const cancelAddMember = () => {
  addingMemberFor.value = null
  memberError.value = ''
}

const refreshExpandedTeam = async (teamId: string) => {
  teamDetail.value = await teamsStore.getDetail(teamId)
}

const addMember = async (teamId: string) => {
  memberError.value = ''

  if (memberMode.value === 'loose' && !newMemberName.value.trim()) {
    memberError.value = t('teamsView.memberNameRequired') as string
    return
  }
  if (memberMode.value === 'linked' && !newMemberUserId.value) {
    memberError.value = t('teamsView.memberUserRequired') as string
    return
  }

  savingMember.value = true
  try {
    if (memberMode.value === 'loose') {
      await teamsStore.addMember(teamId, { name: newMemberName.value.trim(), email: newMemberEmail.value.trim() || undefined })
    } else {
      await teamsStore.addMember(teamId, { userId: newMemberUserId.value })
    }
    await refreshExpandedTeam(teamId)
    cancelAddMember()
  } catch (error: any) {
    memberError.value = error?.response?.data?.detail || (error instanceof Error ? error.message : 'Error al agregar integrante')
  } finally {
    savingMember.value = false
  }
}

const removeMember = async (teamId: string, member: TeamMember) => {
  const confirmed = await dialogStore.confirm(
    t('teamsView.confirmRemoveMember', { name: member.name }) as string
  )
  if (!confirmed) return
  try {
    await teamsStore.removeMember(teamId, member.id)
    await refreshExpandedTeam(teamId)
  } catch (error) {
    console.error('Error al quitar integrante:', error)
  }
}

// =====================================================================
// VINCULAR / CREAR ÉPICA PARA EL EQUIPO
// =====================================================================

const applications = ref<Application[]>([])
const addingEpicFor = ref<string | null>(null)
const epicFormAppId = ref('')
const epicMode = ref<'existing' | 'new'>('existing')
const appEpics = ref<Epic[]>([])
const epicFormEpicId = ref('')
const newEpicTitle = ref('')
const epicError = ref('')
const savingEpic = ref(false)

const startAddEpic = async (teamId: string) => {
  addingEpicFor.value = teamId
  epicFormAppId.value = ''
  epicFormEpicId.value = ''
  newEpicTitle.value = ''
  epicMode.value = 'existing'
  epicError.value = ''
  if (applications.value.length === 0) {
    try {
      applications.value = await applicationsStore.fetchAll() || applicationsStore.applications
    } catch (error) {
      console.error('Error al cargar aplicaciones:', error)
    }
  }
}

const loadAppEpics = async () => {
  epicFormEpicId.value = ''
  appEpics.value = []
  if (!epicFormAppId.value) return
  try {
    appEpics.value = await api.epics.list(epicFormAppId.value)
  } catch (error) {
    console.error('Error al cargar épicas de la aplicación:', error)
  }
}

const cancelAddEpic = () => {
  addingEpicFor.value = null
  epicError.value = ''
}

const linkEpic = async (teamId: string) => {
  epicError.value = ''

  if (!epicFormAppId.value) {
    epicError.value = t('teamsView.selectProjectRequired') as string
    return
  }
  if (epicMode.value === 'existing' && !epicFormEpicId.value) {
    epicError.value = t('teamsView.selectEpicRequired') as string
    return
  }
  if (epicMode.value === 'new' && !newEpicTitle.value.trim()) {
    epicError.value = t('teamsView.epicTitleRequired') as string
    return
  }

  savingEpic.value = true
  try {
    if (epicMode.value === 'existing') {
      await api.epics.update(epicFormEpicId.value, { teamId } as Partial<Epic>)
    } else {
      await api.epics.create(epicFormAppId.value, { title: newEpicTitle.value.trim(), teamId })
    }
    await refreshExpandedTeam(teamId)
    cancelAddEpic()
  } catch (error: any) {
    epicError.value = error?.response?.data?.detail || (error instanceof Error ? error.message : 'Error al vincular la épica')
  } finally {
    savingEpic.value = false
  }
}

onMounted(() => {
  teamsStore.fetchAll()
})
</script>
