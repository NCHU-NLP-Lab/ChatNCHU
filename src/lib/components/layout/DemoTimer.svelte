<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { user, config } from '$lib/stores';
	import { getDemoSession } from '$lib/apis/verification';
	import { userSignOut } from '$lib/apis/auths';
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	let remaining: number | null = null;
	let enabled = false;
	let hasSession = false;
	let intervalId: ReturnType<typeof setInterval> | null = null;
	let warned15 = false;
	let warned5 = false;

	function formatTime(seconds: number): string {
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const s = seconds % 60;
		return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
	}

	async function fetchSession() {
		try {
			const token = localStorage.getItem('token');
			if (!token) return;

			const data = await getDemoSession(token);
			if (data) {
				enabled = data.enabled;
				hasSession = data.has_session;
				if (data.remaining !== null && data.remaining !== undefined) {
					remaining = data.remaining;
				}
			}
		} catch (e) {
			console.error('Failed to fetch demo session:', e);
		}
	}

	async function handleExpired() {
		toast.error($i18n.t('Your session has expired. You will be logged out.'));
		try {
			await userSignOut();
		} catch (e) {
			// ignore
		}
		localStorage.removeItem('token');
		goto('/auth');
	}

	onMount(async () => {
		await fetchSession();

		if (enabled && hasSession) {
			intervalId = setInterval(() => {
				if (remaining !== null && remaining > 0) {
					remaining -= 1;

					// 15-minute warning
					if (remaining <= 900 && remaining > 895 && !warned15) {
						warned15 = true;
						toast.warning($i18n.t('You have 15 minutes remaining.'));
					}

					// 5-minute warning
					if (remaining <= 300 && remaining > 295 && !warned5) {
						warned5 = true;
						toast.error($i18n.t('You have 5 minutes remaining!'));
					}

					// Expired
					if (remaining <= 0) {
						if (intervalId) clearInterval(intervalId);
						handleExpired();
					}
				}
			}, 1000);
		}
	});

	onDestroy(() => {
		if (intervalId) clearInterval(intervalId);
	});
</script>

{#if enabled && hasSession && remaining !== null}
	<div
		class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-mono shadow-lg
		{remaining <= 300
			? 'bg-red-600 text-white animate-pulse'
			: remaining <= 900
				? 'bg-yellow-500 text-black'
				: 'bg-gray-800 text-white dark:bg-gray-700'}"
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			class="h-4 w-4"
			fill="none"
			viewBox="0 0 24 24"
			stroke="currentColor"
			stroke-width="2"
		>
			<circle cx="12" cy="12" r="10" />
			<polyline points="12 6 12 12 16 14" />
		</svg>
		<span>{formatTime(remaining)}</span>
	</div>
{/if}
