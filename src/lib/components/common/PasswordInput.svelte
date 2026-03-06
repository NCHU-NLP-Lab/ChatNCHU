<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let value = '';
	export let placeholder = '';
	export let autocomplete = 'off';
	export let name = '';
	export let required = false;
	export let className = '';

	let showPassword = false;
	let capsLock = false;

	function handleKeyEvent(e: KeyboardEvent) {
		capsLock = e.getModifierState('CapsLock');
	}
</script>

<div class="relative w-full">
	{#if showPassword}
		<input
			bind:value
			type="text"
			class="{className} pr-8"
			{placeholder}
			{autocomplete}
			{name}
			{required}
			on:keydown={handleKeyEvent}
			on:keyup={handleKeyEvent}
		/>
	{:else}
		<input
			bind:value
			type="password"
			class="{className} pr-8"
			{placeholder}
			{autocomplete}
			{name}
			{required}
			on:keydown={handleKeyEvent}
			on:keyup={handleKeyEvent}
		/>
	{/if}

	<button
		type="button"
		class="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
		on:click={() => { showPassword = !showPassword; }}
		tabindex="-1"
		aria-label={showPassword ? 'Hide password' : 'Show password'}
	>
		{#if showPassword}
			<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
				<path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
			</svg>
		{:else}
			<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
				<path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
				<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
			</svg>
		{/if}
	</button>
</div>

{#if capsLock}
	<div class="flex items-center gap-1 mt-1 text-xs text-amber-600 dark:text-amber-400">
		<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-3.5">
			<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
		</svg>
		<span>{$i18n.t('Caps Lock is on')}</span>
	</div>
{/if}
