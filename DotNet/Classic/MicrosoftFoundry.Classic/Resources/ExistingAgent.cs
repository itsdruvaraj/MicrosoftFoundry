using Azure.AI.Agents.Persistent;
using MicrosoftFoundry.Classic.Common;

namespace MicrosoftFoundry.Classic.Resources;

/// <summary>
/// Demonstrates retrieving and conversing with an existing agent using Azure.AI.Agents.Persistent SDK.
/// </summary>
public sealed class ExistingAgent
{
    private readonly FoundryClientFactory _factory;
    private readonly string _agentId;
    private readonly string? _additionalInstructions;

    /// <summary>
    /// Initializes a new instance of the <see cref="ExistingAgent"/> class.
    /// </summary>
    /// <param name="factory">The Foundry client factory.</param>
    /// <param name="agentId">The ID of the existing agent to retrieve.</param>
    /// <param name="additionalInstructions">Optional additional instructions to override/augment the agent's prompt at runtime.</param>
    public ExistingAgent(FoundryClientFactory factory, string agentId, string? additionalInstructions = null)
    {
        ArgumentNullException.ThrowIfNull(factory);
        ArgumentException.ThrowIfNullOrWhiteSpace(agentId);
        _factory = factory;
        _agentId = agentId;
        _additionalInstructions = additionalInstructions;
    }

    /// <summary>
    /// Retrieves an existing agent and runs a conversational example.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    public async Task RunAsync(CancellationToken cancellationToken = default)
    {
        Console.WriteLine("=== Existing Agent Example: Retrieve & Converse ===");
        Console.WriteLine();

        PersistentAgentThread? thread = null;

        try
        {
            // Retrieve the existing agent by ID
            var client = _factory.GetClient();
            Console.WriteLine($"Retrieving existing agent with ID: {_agentId}...");
            PersistentAgent agent = await client.Administration.GetAgentAsync(_agentId, cancellationToken);
            Console.WriteLine($"Agent retrieved: {agent.Name} (Model: {agent.Model})");

            if (!string.IsNullOrWhiteSpace(_additionalInstructions))
            {
                Console.WriteLine($"Additional instructions: {_additionalInstructions}");
            }

            // Create a new thread for this conversation
            thread = await _factory.CreateThreadAsync(cancellationToken);
            Console.WriteLine($"Thread created: {thread.Id}");
            Console.WriteLine();

            // Interactive conversation loop
            Console.WriteLine("Type your messages below. Enter an empty line to exit.");
            Console.WriteLine();

            while (true)
            {
                Console.Write("User: ");
                var userInput = Console.ReadLine();

                if (string.IsNullOrWhiteSpace(userInput))
                {
                    Console.WriteLine("Ending conversation.");
                    break;
                }

                var run = await _factory.SendMessageAndRunAsync(
                    thread,
                    agent,
                    userInput,
                    additionalInstructions: _additionalInstructions,
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
            // Only clean up the thread — the agent is pre-existing and should not be deleted
            Console.WriteLine("Cleaning up thread...");
            await _factory.CleanupAsync(agent: null, thread, cancellationToken);
            Console.WriteLine("Cleanup complete.");
        }
    }
}
