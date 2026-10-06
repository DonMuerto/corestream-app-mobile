/**
 * Store de Equipos (Team) - CoreStream
 *
 * Un Team agrupa Épicas (posiblemente repartidas entre varias Application)
 * para poder ver y evaluar el trabajo de un equipo de estudiantes como una
 * unidad ("mini-proyecto"). Contexto completo: Alloxentric opera como
 * software factory con convenio DuocUC/UTEM; cada semestre reparte decenas
 * de proyectos entre muchos equipos, y cada equipo suele trabajar un
 * conjunto propio de épicas. Los estudiantes rara vez usan CoreStream —
 * quien lo usa a diario es el Team Leader interno que hace seguimiento por
 * fuera — por eso los integrantes (members) pueden ser nombres sueltos sin
 * cuenta, o vincularse a un User real si Karina necesita control fino
 * (asignar tickets con precisión a esa persona).
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Team, TeamDetail, TeamMember } from '@/types'
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

  const addMember = async (
    teamId: string,
    data: { name?: string; email?: string; userId?: string }
  ): Promise<TeamMember> => {
    const member = await api.teams.addMember(teamId, data)
    const index = teams.value.findIndex((t) => t.id === teamId)
    if (index !== -1) {
      teams.value[index] = { ...teams.value[index], memberCount: teams.value[index].memberCount + 1 }
    }
    return member
  }

  const removeMember = async (teamId: string, memberId: string): Promise<void> => {
    await api.teams.removeMember(teamId, memberId)
    const index = teams.value.findIndex((t) => t.id === teamId)
    if (index !== -1) {
      teams.value[index] = { ...teams.value[index], memberCount: Math.max(0, teams.value[index].memberCount - 1) }
    }
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
    addMember,
    removeMember,
  }
})
