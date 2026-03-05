<script lang="ts">
	import { onMount, getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let value = 'user';
	export let disabled = false;

	let open = false;

	const ROLES = [
		{ code: 'pending', type: 'muted' },
		{ code: 'user', type: 'success' },
		{ code: 'admin', type: 'info' },
		{ code: 'suspended', type: 'error' }
	];

	const badgeClasses: Record<string, string> = {
		info: 'bg-blue-500/20 text-blue-700 dark:text-blue-200',
		success: 'bg-green-500/20 text-green-700 dark:text-green-200',
		error: 'bg-red-500/20 text-red-700 dark:text-red-200',
		muted: 'bg-gray-500/20 text-gray-700 dark:text-gray-200'
	};

	const hoverClasses: Record<string, string> = {
		info: 'hover:bg-blue-500/30',
		success: 'hover:bg-green-500/30',
		error: 'hover:bg-red-500/30',
		muted: 'hover:bg-gray-500/30'
	};

	function getRole(code: string) {
		return ROLES.find((r) => r.code === code) ?? ROLES[0];
	}

	function select(code: string) {
		if (disabled) return;
		value = code;
		open = false;
	}

	function handleClickOutside(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.role-dropdown')) {
			open = false;
		}
	}

	onMount(() => {
		document.addEventListener('click', handleClickOutside);
		return () => document.removeEventListener('click', handleClickOutside);
	});
</script>

<div class="role-dropdown relative">
	<button
		class="flex items-center rounded-sm px-2 py-1.5 text-xs font-bold uppercase transition
			{badgeClasses[getRole(value).type]}
			{disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer ' + hoverClasses[getRole(value).type]}"
		type="button"
		on:click|stopPropagation={() => { if (!disabled) open = !open; }}
	>
		{$i18n.t(value)}
	</button>

	{#if open && !disabled}
		<div
			class="absolute left-0 top-full mt-1 rounded-lg border border-gray-200 dark:border-gray-700
				bg-white dark:bg-gray-850 shadow-lg overflow-hidden z-50 min-w-[120px]"
		>
			{#each ROLES as role}
				<button
					class="w-full px-3 py-1.5 text-xs text-left whitespace-nowrap transition flex items-center gap-2
						{role.code === value
						? badgeClasses[role.type] + ' font-bold uppercase'
						: 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}"
					type="button"
					on:click|stopPropagation={() => select(role.code)}
				>
					<span class="inline-block w-fit px-1.5 py-0.5 rounded-sm text-xs font-bold uppercase {badgeClasses[role.type]}">
						{$i18n.t(role.code)}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
