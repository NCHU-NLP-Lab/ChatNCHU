<script lang="ts">
	import { onMount } from 'svelte';
	import { changeLanguage } from '$lib/i18n';
	import i18next from 'i18next';

	let open = false;
	let currentLang = 'en-US';

	const LANGS = [
		{ code: 'zh-TW', label: '繁中' },
		{ code: 'en-US', label: 'EN' },
		{ code: 'ja-JP', label: '日本語' },
		{ code: 'ko-KR', label: '한국어' },
		{ code: 'vi-VN', label: 'Tiếng Việt' },
		{ code: 'th-TH', label: 'ไทย' },
		{ code: 'id-ID', label: 'Indonesia' }
	];

	function getLangLabel(code: string): string {
		return LANGS.find((l) => l.code === code)?.label ?? code;
	}

	async function switchLang(code: string) {
		await changeLanguage(code);
		localStorage.setItem('locale', code);
		currentLang = code;
		open = false;
	}

	function handleClickOutside(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.lang-switcher')) {
			open = false;
		}
	}

	onMount(() => {
		currentLang = i18next.language || localStorage.getItem('locale') || 'en-US';
		document.addEventListener('click', handleClickOutside);
		return () => document.removeEventListener('click', handleClickOutside);
	});
</script>

<div class="lang-switcher relative">
	<button
		class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium
			bg-white/80 dark:bg-gray-800/80 text-gray-700 dark:text-gray-200
			hover:bg-gray-100 dark:hover:bg-gray-700 backdrop-blur shadow-sm transition"
		on:click|stopPropagation={() => (open = !open)}
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			class="h-3.5 w-3.5"
			fill="none"
			viewBox="0 0 24 24"
			stroke="currentColor"
			stroke-width="2"
		>
			<circle cx="12" cy="12" r="10" />
			<path d="M2 12h20" />
			<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
		</svg>
		<span>{getLangLabel(currentLang)}</span>
	</button>

	{#if open}
		<div
			class="absolute right-0 top-full mt-1 rounded-lg border border-gray-200 dark:border-gray-700
				bg-white dark:bg-gray-850 shadow-lg overflow-hidden z-50 min-w-[130px]"
		>
			{#each LANGS as lang}
				<button
					class="w-full px-3 py-1.5 text-xs text-left whitespace-nowrap transition
						{lang.code === currentLang
						? 'bg-gray-100 dark:bg-gray-700 font-semibold text-gray-900 dark:text-white'
						: 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}"
					on:click|stopPropagation={() => switchLang(lang.code)}
				>
					{lang.label}
				</button>
			{/each}
		</div>
	{/if}
</div>
