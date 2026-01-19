---
name: vue-pinia-store
description: Pinia store scaffolding patterns for Vue 3. Use when creating Pinia stores, state management, actions, getters, or Vue composition API stores.
---

# Pinia Store Patterns

## Installation
```bash
npm install pinia
```

## Setup in main.ts
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

## Basic Store (Options API Style)
```typescript
// stores/counter.ts
import { defineStore } from 'pinia'

export const useCounterStore = defineStore('counter', {
  state: () => ({
    count: 0,
    name: 'Counter'
  }),
  
  getters: {
    doubleCount: (state) => state.count * 2,
    
    // Getter with args
    countPlusN: (state) => {
      return (n: number) => state.count + n
    }
  },
  
  actions: {
    increment() {
      this.count++
    },
    
    async fetchCount() {
      const response = await fetch('/api/count')
      this.count = await response.json()
    }
  }
})
```

## Setup Store (Composition API Style) - Recommended
```typescript
// stores/user.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  // State
  const user = ref<User | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!user.value)
  const fullName = computed(() => 
    user.value ? `${user.value.firstName} ${user.value.lastName}` : ''
  )

  // Actions
  async function login(email: string, password: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!response.ok) throw new Error('Login failed')
      user.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  function logout() {
    user.value = null
  }

  return { user, loading, error, isAuthenticated, fullName, login, logout }
})
```

## TypeScript Interfaces
```typescript
// stores/types.ts
export interface User {
  id: number
  email: string
  firstName: string
  lastName: string
}

export interface Product {
  id: number
  name: string
  price: number
  quantity: number
}

export interface CartItem {
  product: Product
  quantity: number
}
```

## CRUD Store Pattern
```typescript
// stores/products.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Product } from './types'

export const useProductStore = defineStore('products', () => {
  const items = ref<Product[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const getById = computed(() => {
    return (id: number) => items.value.find(item => item.id === id)
  })
  
  const totalCount = computed(() => items.value.length)

  // Actions
  async function fetchAll() {
    loading.value = true
    try {
      const res = await fetch('/api/products')
      items.value = await res.json()
    } catch (e) {
      error.value = 'Failed to fetch products'
    } finally {
      loading.value = false
    }
  }

  async function create(product: Omit<Product, 'id'>) {
    const res = await fetch('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(product)
    })
    const newProduct = await res.json()
    items.value.push(newProduct)
    return newProduct
  }

  async function update(id: number, updates: Partial<Product>) {
    const res = await fetch(`/api/products/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    })
    const updated = await res.json()
    const index = items.value.findIndex(p => p.id === id)
    if (index !== -1) items.value[index] = updated
    return updated
  }

  async function remove(id: number) {
    await fetch(`/api/products/${id}`, { method: 'DELETE' })
    items.value = items.value.filter(p => p.id !== id)
  }

  return { items, loading, error, getById, totalCount, fetchAll, create, update, remove }
})
```

## Cart Store (Composing Stores)
```typescript
// stores/cart.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useProductStore } from './products'
import type { CartItem } from './types'

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([])
  const productStore = useProductStore()

  const totalItems = computed(() => 
    items.value.reduce((sum, item) => sum + item.quantity, 0)
  )

  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => 
      sum + item.product.price * item.quantity, 0
    )
  )

  function addItem(productId: number, quantity = 1) {
    const product = productStore.getById(productId)
    if (!product) return

    const existing = items.value.find(i => i.product.id === productId)
    if (existing) {
      existing.quantity += quantity
    } else {
      items.value.push({ product, quantity })
    }
  }

  function removeItem(productId: number) {
    items.value = items.value.filter(i => i.product.id !== productId)
  }

  function clearCart() {
    items.value = []
  }

  return { items, totalItems, totalPrice, addItem, removeItem, clearCart }
})
```

## Store with Persistence
```typescript
// stores/settings.ts
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref(localStorage.getItem('theme') || 'light')
  const locale = ref(localStorage.getItem('locale') || 'en')

  // Persist on change
  watch(theme, (val) => localStorage.setItem('theme', val))
  watch(locale, (val) => localStorage.setItem('locale', val))

  function setTheme(newTheme: 'light' | 'dark') {
    theme.value = newTheme
  }

  function setLocale(newLocale: string) {
    locale.value = newLocale
  }

  return { theme, locale, setTheme, setLocale }
})
```

## Usage in Components
```vue
<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import { useCartStore } from '@/stores/cart'
import { storeToRefs } from 'pinia'

const userStore = useUserStore()
const cartStore = useCartStore()

// Destructure with reactivity preserved
const { user, isAuthenticated, loading } = storeToRefs(userStore)
const { totalItems, totalPrice } = storeToRefs(cartStore)

// Actions can be destructured directly
const { login, logout } = userStore
const { addItem, clearCart } = cartStore

async function handleLogin() {
  await login('user@example.com', 'password')
}
</script>

<template>
  <div v-if="loading">Loading...</div>
  <div v-else-if="isAuthenticated">
    <p>Welcome, {{ user?.firstName }}</p>
    <p>Cart: {{ totalItems }} items (${{ totalPrice }})</p>
    <button @click="logout">Logout</button>
  </div>
  <button v-else @click="handleLogin">Login</button>
</template>
```

## Reset Store State
```typescript
// In component
const store = useUserStore()
store.$reset() // Resets to initial state (options API stores only)

// For setup stores, define reset manually
function $reset() {
  user.value = null
  loading.value = false
  error.value = null
}
```

## Subscribe to Changes
```typescript
const userStore = useUserStore()

// Subscribe to state changes
userStore.$subscribe((mutation, state) => {
  console.log('State changed:', mutation.type, state)
})

// Subscribe to actions
userStore.$onAction(({ name, args, after, onError }) => {
  console.log(`Action ${name} called with`, args)
  
  after((result) => {
    console.log(`Action ${name} finished with`, result)
  })
  
  onError((error) => {
    console.error(`Action ${name} failed:`, error)
  })
})
```

## File Structure
```
src/
├── stores/
│   ├── index.ts      # Re-export all stores
│   ├── types.ts      # Shared interfaces
│   ├── user.ts
│   ├── products.ts
│   ├── cart.ts
│   └── settings.ts
```

## stores/index.ts
```typescript
export { useUserStore } from './user'
export { useProductStore } from './products'
export { useCartStore } from './cart'
export { useSettingsStore } from './settings'
```
```

## Verify Installation
```
/skills
```

Or test:
```
"Help me create a Pinia store for managing a todo list"
