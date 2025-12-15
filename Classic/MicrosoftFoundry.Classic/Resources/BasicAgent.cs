using Azure.AI.Agents.Persistent;
using MicrosoftFoundry.Classic.Common;

namespace MicrosoftFoundry.Classic.Resources;

/// <summary>
/// Demonstrates a basic agent implementation using Azure.AI.Agents.Persistent SDK.
/// </summary>
public sealed class BasicAgent
{
    private readonly FoundryClientFactory _factory;

    /// <summary>
    /// Initializes a new instance of the <see cref="BasicAgent"/> class.
    /// </summary>
    /// <param name="factory">The Foundry client factory.</param>
    public BasicAgent(FoundryClientFactory factory)
    {
        ArgumentNullException.ThrowIfNull(factory);
        _factory = factory;
    }

    /// <summary>
    /// Runs a conversational agent example with multiple exchanges.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    public async Task RunAsync(CancellationToken cancellationToken = default)
    {
        Console.WriteLine("=== Basic Agent Example: Conversation ===");
        Console.WriteLine();

        PersistentAgent? agent = null;
        PersistentAgentThread? thread = null;

        try
        {
            // Create a helpful assistant
            Console.WriteLine("Creating assistant agent...");
            agent = await _factory.CreateAgentAsync(
                name: "Foundry-Classic-Basic-Agent",
                instructions: "You are a helpful assistant. Be concise and friendly in your responses.",
                cancellationToken: cancellationToken);
            Console.WriteLine($"Agent created: {agent.Name}");

            // Create a thread
            thread = await _factory.CreateThreadAsync(cancellationToken);
            Console.WriteLine($"Thread created: {thread.Id}");
            Console.WriteLine();

            // Have a conversation
            var questions = new[]
            {
                "Hello! What can you help me with?",
                "Can you explain what an AI agent is in simple terms?",
                "Thanks! That was helpful."
            };

            foreach (var question in questions)
            {
                Console.WriteLine($"User: {question}");

                var run = await _factory.SendMessageAndRunAsync(
                    thread,
                    agent,
                    question,
                    cancellationToken: cancellationToken);

                if (run.Status == RunStatus.Completed)
                {
                    await _factory.DisplayLatestResponseAsync(thread.Id, "Assistant: ", cancellationToken);
                }
                else
                {
                    Console.WriteLine($"Run failed with status: {run.Status}");
                }

                Console.WriteLine();
            }
        }
        finally
        {
            Console.WriteLine("Cleaning up resources...");
            await _factory.CleanupAsync(agent, thread, cancellationToken);
            Console.WriteLine("Cleanup complete.");
        }
    }
}
