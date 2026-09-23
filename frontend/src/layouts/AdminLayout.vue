<!--
  Layout para sección de administración

  Proporciona navegación sidebar y estructura común para todas las vistas admin.
-->
<template>
  <div class="flex h-screen bg-[var(--bg-app)] overflow-hidden">
    <!-- Overlay para móvil -->
    <div v-if="isSidebarOpen" @click="toggleSidebar" class="fixed inset-0 bg-black/50 z-40 md:hidden"></div>

    <!-- Sidebar -->
    <aside 
      id="admin-sidebar"
      :class="[
      'bg-[var(--bg-sidebar)] border-r border-[var(--border-subtle)] z-50 fixed md:relative h-full transition-transform duration-300 w-64',
      isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
    ]"
    aria-label="Navegación principal"
    >
      <nav class="p-6 space-y-4">
        <h2 class="font-bold text-lg text-[var(--text-primary)] mb-6">
          {{ t('nav.administration') }}
        </h2>

        <router-link
          to="/admin/builder"
          class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
          active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
        >
          {{ t('nav.builder') }}
        </router-link>

        <!-- Analytics/Incidents/Meetings/Team: TEAM_LEADER manages the
             team's day-to-day, including inviting developers (the backend
             already allows it in analytics.py, incidents.py, meetings.py,
             users.py and invitations.py), so they see these too.
             code-docs/support stay ADMIN-only — platform administration
             itself (system config, internal support). -->
        <template v-if="isAdminOrLeader">
          <router-link
            to="/admin/analytics"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.analytics') }}
          </router-link>

          <router-link
            to="/admin/incidents"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            Incidentes
          </router-link>

          <router-link
            to="/admin/meetings"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            Reuniones
          </router-link>

          <router-link
            to="/admin/team"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.team') }}
          </router-link>

          <router-link
            to="/dev/teams"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.teams') }}
          </router-link>
        </template>

        <!--
          Reciprocal del bloque que se agregó en DeveloperLayout: Team
          Leader entra aquí desde el sidebar de Desarrollo, y sin esto no
          tenía forma de volver a Workbench salvo con el botón "atrás" del
          navegador. (Equipos vive arriba, junto a Analítica/Incidentes/
          Reuniones, porque también es relevante para ADMIN.)
        -->
        <template v-if="!isAdmin && isAdminOrLeader">
          <hr class="border-[var(--border-subtle)]" />
          <p class="px-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            {{ t('nav.development') }}
          </p>

          <router-link
            to="/dev/workbench"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.workbench') }}
          </router-link>

          <router-link
            to="/dev/team-assignment"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.teamAssignment') }}
          </router-link>

          <router-link
            to="/dev/support"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.support') }}
          </router-link>
        </template>

        <template v-if="isAdmin">
          <router-link
            to="/admin/code-docs"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.documentation') }}
          </router-link>

          <router-link
            to="/admin/support"
            class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
            active-class="bg-[var(--bg-panel)] text-[var(--teal)] font-bold shadow-sm"
          >
            {{ t('nav.support') }}
          </router-link>
        </template>

      </nav>
    </aside>

    <!-- Contenido principal -->
    <main class="flex-1 overflow-auto">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * AdminLayout - Componente de estructura para vistas de administración
 */
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'
import { eventBus } from '@/utils/eventBus'

const authStore = useAuthStore()
const { t } = useI18n()

const isAdmin = computed(() => authStore.userRole === 'ADMIN')
const isAdminOrLeader = computed(() => isAdmin.value || authStore.userRole === 'TEAM_LEADER')

const isSidebarOpen = ref(false)
const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

// El botón hamburguesa vive en AppHeader (cada vista de admin lo renderiza),
// así que el toggle del sidebar de este layout se coordina por eventBus.
onMounted(() => eventBus.on('toggle-sidebar', toggleSidebar))
onUnmounted(() => eventBus.off('toggle-sidebar', toggleSidebar))
</script>
