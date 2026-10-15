OUT="$(cd "$(dirname "$0")/../.." && pwd)/guia_interativo.html"; cd "$(dirname "$0")"
{
cat <<'EOF'
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guia do rpg-ia-master</title>
<meta name="description" content="Guia interativo e pedagógico de como funciona o rpg-ia-master: grafo de agentes, IA, memória, combate, infraestrutura e processo.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
EOF
cat style.css
echo '</style></head><body>'
cat body1.html body2.html body3.html
echo '<script>'
cat lib.js data_graphs.js data_steps.js widgets.js
cat <<'EOF'
document.addEventListener('DOMContentLoaded', () => {
  mountDiagrams(); mountSteppers(); mountQuizzes(); mountTabs(); mountToc(); mountFilters();
  mountAttack(); mountRouted(); mountPrice(); mountBudget(); mountScore(); mountXP(); mountSSE(); mountClaim(); mountVis();
});
</script></body></html>
EOF
} > "$OUT"
