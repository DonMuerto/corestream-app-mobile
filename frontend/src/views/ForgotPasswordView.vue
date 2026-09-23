<!--
  Página pública para pedir el enlace de reset de contraseña.
  Antes la única forma de recuperar una cuenta era que un ADMIN generara una
  contraseña temporal a mano (POST /users/{id}/reset-password).
-->
<template>
  <div
    class="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 transition-colors duration-300"
    :class="isDark
      ? 'bg-[#0A1A20]'
      : 'bg-gradient-to-br from-[#E6F8F7] via-[#F7FDED] to-[#CDF1F0]'"
  >
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-2xl font-bold" :class="isDark ? 'text-white' : 'text-[#142730]'">CoreStream</h1>
      </div>

      <div
        class="rounded-2xl p-10 space-y-5 transition-colors duration-300"
        :class="isDark
          ? 'bg-[#142730] shadow-[0_20px_60px_rgba(0,0,0,0.4)]'
          : 'bg-white shadow-[0_20px_60px_rgba(6,183,178,0.15),0_4px_16px_rgba(0,0,0,0.08)]'"
      >
        <!-- Enlace enviado -->
        <div v-if="sent" class="text-center space-y-4">
          <p class="text-sm" :class="isDark ? 'text-[#A1A9AC]' : 'text-[#5A686E]'">
            Si el correo existe, te enviamos un enlace para restablecer tu contraseña. Revisa tu bandeja
            (y spam) — es válido por 1 hora.
          </p>
          <router-link
            to="/login"
            class="inline-block w-full py-3 px-4 rounded-xl bg-[#ADEA4B] text-[#142730] text-base font-bold hover:bg-[#B5EC5D] transition-colors duration-200"
          >
            Ir a iniciar sesión
          </router-link>
        </div>

        <!-- Formulario -->
        <form v-else @submit.prevent="onSubmit" class="space-y-5">
          <p class="text-sm" :class="isDark ? 'text-[#A1A9AC]' : 'text-[#5A686E]'">
            Ingresa tu correo y te mandamos un enlace para elegir una nueva contraseña.
          </p>

          <div>
            <label class="block text-sm font-medium mb-2" :class="isDark ? 'text-[#A1A9AC]' : 'text-[#5A686E]'">
              Correo
            </label>
            <input
              v-model="email"
              type="email"
              required
              autocomplete="email"
              class="w-full rounded-xl border px-4 py-3 text-sm focus:outline-none focus:ring-2 transition-all"
              :class="isDark
                ? 'bg-[#0A1A20] border-[#2A4A55] text-white focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'
                : 'bg-white border-[#D0D4D6] text-[#142730] focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'"
            />
          </div>

          <p v-if="formError" class="text-sm text-[#DC2626] bg-[#FEE2E2] px-4 py-3 rounded-lg">
            {{ formError }}
          </p>

          <button
            type="submit"
            :disabled="submitting"
            class="w-full py-3 px-4 rounded-xl bg-[#ADEA4B] text-[#142730] text-base font-bold hover:bg-[#B5EC5D] disabled:opacity-50 transition-colors duration-200"
          >
            {{ submitting ? 'Enviando...' : 'Enviar enlace' }}
          </button>

          <router-link
            to="/login"
            class="block text-center text-sm underline"
            :class="isDark ? 'text-[#06B7B2]' : 'text-[#0891B2]'"
          >
            Volver a iniciar sesión
          </router-link>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useThemeStore } from '@/stores'
import api from '@/services/api'

const themeStore = useThemeStore()
const isDark = computed(() => themeStore.isDark())

const email = ref('')
const submitting = ref(false)
const formError = ref<string | null>(null)
const sent = ref(false)

const onSubmit = async () => {
  formError.value = null
  submitting.value = true
  try {
    await api.auth.requestPasswordReset({ email: email.value.trim() })
    sent.value = true
  } catch (err: any) {
    formError.value = err?.response?.data?.detail || 'No se pudo procesar la solicitud'
  } finally {
    submitting.value = false
  }
}
</script>
