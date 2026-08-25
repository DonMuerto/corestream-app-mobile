/**
 * Store de Equipos (Team) - CoreStream
 *
 * Un Team agrupa Épicas (posiblemente repartidas entre varias Application)
 * para poder ver y evaluar el trabajo de un equipo de estudiantes como una
 * unidad ("mini-proyecto"). Contexto completo: Alloxentric opera como
 * software factory con convenio DuocUC/UTEM; cada semestre reparte decenas
 * de proyectos entre muchos equipos, y cada equipo suele trabajar un
 * conjunto propio de épicas. Los estudiantes no usan CoreStream — quien lo
 * usa es el Team Leader interno que hace seguimiento por fuera, por eso
 * esto es un catálogo de etiquetas y no un sistema de membresías/roles.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Team, TeamDetail } from '@/types'
import { api } from '@/services/api'

export const useTeamsStore = defineStore('teams', () => {
  const teams = ref<Team[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchAll = async (): Promise<Team[] | undefined> => {
    isLoading.value = true
    error.value = null
    try {
      teams.value = await api.teams.list()
      return teams.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al obtener equipos'
      console.error('Error en fetchAll (teams):', err)
    } finally {
      isLoading.value = false
    }
  }

  const getDetail = async (teamId: string): Promise<TeamDetail> => {
    return api.teams.getById(teamId)
  }

  const create = async (data: { name: string; description?: string }): Promise<Team> => {
    const created = await api.teams.create(data)
    teams.value.push(created)
    return created
  }

  const update = async (teamId: string, data: { name?: string; description?: string }): Promise<Team> => {
    const updated = await api.teams.update(teamId, data)
    const index = teams.value.findIndex((t) => t.id === teamId)
    if (index !== -1) {
      teams.value[index] = updated
    }
    return updated
  }

  const remove = async (teamId: string): Promise<void> => {
    await api.teams.delete(teamId)
    teams.value = teams.value.filter((t) => t.id !== teamId)
  }

  return {
    teams,
    isLoading,
    error,
    fetchAll,
    getDetail,
    create,
    update,
    remove,
  }
})
