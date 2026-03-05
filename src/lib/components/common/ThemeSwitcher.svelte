<script lang="ts">
	import { onMount } from 'svelte';
	import { theme } from '$lib/stores';

	let open = false;
	let currentTheme = 'system';

	const themes = ['dark', 'light', 'rose-pine dark', 'rose-pine-dawn light', 'oled-dark'];

	const THEME_OPTIONS = [
		{ code: 'system', label: 'System' },
		{ code: 'light', label: 'Light' },
		{ code: 'dark', label: 'Dark' }
	];

	const applyTheme = (_theme: string) => {
		let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

		if (_theme === 'system') {
			themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}

		if (themeToApply === 'dark' && !_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#333');
			document.documentElement.style.setProperty('--color-gray-850', '#262626');
			document.documentElement.style.setProperty('--color-gray-900', '#171717');
			document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
		}

		themes
			.filter((e) => e !== themeToApply)
			.forEach((e) => {
				e.split(' ').forEach((e) => {
					document.documentElement.classList.remove(e);
				});
			});

		themeToApply.split(' ').forEach((e) => {
			document.documentElement.classList.add(e);
		});

		const metaThemeColor = document.querySelector('meta[name="theme-color"]');
		if (metaThemeColor) {
			if (_theme.includes('system')) {
				const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
					? 'dark'
					: 'light';
				metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
			} else {
				metaThemeColor.setAttribute(
					'content',
					_theme === 'dark' ? '#171717' : '#ffffff'
				);
			}
		}

		if (typeof window !== 'undefined' && window.applyTheme) {
			window.applyTheme();
		}
	};

	function switchTheme(code: string) {
		currentTheme = code;
		theme.set(code);
		localStorage.setItem('theme', code);
		applyTheme(code);
		open = false;
	}

	function handleClickOutside(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.theme-switcher')) {
			open = false;
		}
	}

	onMount(() => {
		currentTheme = localStorage.getItem('theme') ?? 'system';
		document.addEventListener('click', handleClickOutside);
		return () => document.removeEventListener('click', handleClickOutside);
	});
</script>

<div class="theme-switcher relative">
	<button
		class="flex items-center rounded-lg p-1.5 text-xs font-medium
			bg-white/80 dark:bg-gray-800/80 text-gray-700 dark:text-gray-200
			hover:bg-gray-100 dark:hover:bg-gray-700 backdrop-blur shadow-sm transition"
		on:click|stopPropagation={() => (open = !open)}
		title="Theme"
	>
		{#if currentTheme === 'light'}
			<!-- Sun -->
			<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
			</svg>
		{:else if currentTheme === 'dark'}
			<!-- Moon -->
			<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
			</svg>
		{:else}
			<!-- Monitor (System) -->
			<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
			</svg>
		{/if}
	</button>

	{#if open}
		<div
			class="absolute right-0 top-full mt-1 rounded-lg border border-gray-200 dark:border-gray-700
				bg-white dark:bg-gray-850 shadow-lg overflow-hidden z-50 min-w-[120px]"
		>
			{#each THEME_OPTIONS as t}
				<button
					class="w-full px-3 py-1.5 text-xs text-left whitespace-nowrap transition flex items-center gap-2
						{t.code === currentTheme
						? 'bg-gray-100 dark:bg-gray-700 font-semibold text-gray-900 dark:text-white'
						: 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}"
					on:click|stopPropagation={() => switchTheme(t.code)}
				>
					{#if t.code === 'light'}
						<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
						</svg>
					{:else if t.code === 'dark'}
						<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
						</svg>
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
						</svg>
					{/if}
					{t.label}
				</button>
			{/each}
		</div>
	{/if}
</div>
