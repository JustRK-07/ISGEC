export function FinalCTA() {
  return (
    <section className="py-24 px-6 bg-bg-dark text-white text-center" id="contact">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-h2 font-bold mb-6">Ready to catch what your last review missed?</h2>
        <div className="flex gap-3 justify-center flex-wrap">
          <a
            href="mailto:demo@adv.example?subject=Book%20a%2020-min%20Demo"
            className="bg-accent hover:bg-accent-hover text-white font-medium px-6 py-3 rounded"
          >
            Book a 20-min Demo
          </a>
          <a
            href="/upload"
            className="border border-text-muted/50 hover:border-accent text-white font-medium px-6 py-3 rounded"
          >
            Run a Free First Check
          </a>
        </div>
      </div>
    </section>
  );
}
